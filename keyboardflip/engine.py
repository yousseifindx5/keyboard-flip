"""The engine: hotkey -> copy selection -> change text -> paste."""
import json
import os
import re
import sys
import threading
import time
from collections import deque

from . import winapi
from .config import CONFIG_DIR, HISTORY_FILE
from .i18n import lang_name, tr
from .layouts import DEFAULT_LAYOUTS, LANGUAGES, RTL_SCRIPTS, convert_between, script_counts
from .log import log_error as _log_error
from .textcase import cycle_case

UNDO_ID, CASE_ID, SNIPPETS_ID = 1000, 1001, 1002
SPECIAL_HOTKEYS = ((UNDO_ID, "undo_hotkey"), (CASE_ID, "case_hotkey"), (SNIPPETS_ID, "snippets_hotkey"))
UNDO_WINDOW = 30     # seconds after a change during which Undo is allowed
UNDO_DEPTH = 10      # how many changes in a row can be undone
HISTORY_MAX = 50
PREVIEW_TIMEOUT = 12  # seconds the preview waits for Enter / Esc
RESELECT_MAX = 3000   # longest text that is selected again after a case change
STALE_LOCK = 20       # seconds after which a stuck worker is abandoned
OWN_PROCESSES = {os.path.basename(sys.executable).lower(), "keyboardflip.exe", "python.exe", "pythonw.exe"}


class Engine:
    def __init__(self, cfg, notify):
        """notify(text, ok) is called from worker threads; it must be thread-safe."""
        self.cfg = cfg
        self.notify = notify
        # request(kind, *args) asks the window to do something (preview, snippets menu,
        # refresh the history). Set by main.py; it must be thread-safe too.
        self.request = None
        self.listener = winapi.HotkeyListener(self._on_hotkey)
        self.double_tap = winapi.DoubleTapListener(self._on_double_tap)
        self.bindings = {}
        self.failed = []
        self.active = 0
        self.history = deque(maxlen=HISTORY_MAX)  # newest first; memory only, never saved
        self.undo_stack = deque(maxlen=UNDO_DEPTH)
        self._last_case = None
        self.practice = False  # True while the welcome tour is open (it converts inside our own window)
        self._lock = threading.Lock()
        self._busy_since = 0.0

    # ------------------------------------------------------------------ setup
    def _valid_rules(self):
        langs = set(self.cfg["languages"])
        seen, out = set(), []
        for rule in self.cfg["rules"]:
            if not rule.get("enabled", True):
                continue
            if rule["src"] not in langs or rule["dst"] not in langs or rule["src"] == rule["dst"]:
                continue
            key = winapi.normalize_hotkey(rule["hotkey"])
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rule)
        return out

    def reload(self):
        """(Re)register all shortcuts. Returns the list of shortcuts Windows refused."""
        self.listener.stop()
        self.double_tap.stop()
        self.bindings, self.failed, self.active = {}, [], 0
        settings = self.cfg["settings"]
        if not settings.get("enabled", True):
            return []
        items = []
        for n, rule in enumerate(self._valid_rules(), start=1):
            self.bindings[n] = rule
            items.append((n, rule["hotkey"]))
        taken = {winapi.normalize_hotkey(hk) for _, hk in items}
        all_items = list(items)
        for hid, name in SPECIAL_HOTKEYS:
            hotkey = settings.get(name, "")
            key = winapi.normalize_hotkey(hotkey) if hotkey else ""
            if key and key not in taken:
                taken.add(key)
                all_items.append((hid, hotkey))
        self.listener.start(all_items)
        self.failed = list(self.listener.failed)
        self.active = sum(1 for _, hk in items if hk not in self.failed)
        self.double_tap.start(settings.get("double_tap_key", "off"))
        return self.failed

    def suspend(self):
        self.listener.stop()
        self.double_tap.stop()

    def stop(self):
        self.listener.stop()
        self.double_tap.stop()

    # ------------------------------------------------------------- conversion
    def convert(self, rule, text):
        src, dst = rule["src"], rule["dst"]
        if rule.get("bidirectional"):
            counts = script_counts(text)
            if counts[LANGUAGES[dst]["script"]] > counts[LANGUAGES[src]["script"]]:
                src, dst = dst, src
        layouts = self.cfg["layouts"]
        result = convert_between(text, layouts.get(src, DEFAULT_LAYOUTS[src]),
                                 layouts.get(dst, DEFAULT_LAYOUTS[dst]))
        return result, src, dst

    # ---------------------------------------------------------------- hotkeys
    def _on_hotkey(self, hid):
        if hid == UNDO_ID:
            target = self._undo
        elif hid == CASE_ID:
            target = self._change_case
        elif hid == SNIPPETS_ID:
            target = self._open_snippets
        else:
            rule = self.bindings.get(hid)
            if not rule:
                return
            threading.Thread(target=self._run, args=(rule,), daemon=True).start()
            return
        threading.Thread(target=target, daemon=True).start()

    def _on_double_tap(self):
        """Double-tapped Shift/Ctrl: run the conversion chosen in Settings."""
        rules = self._valid_rules()
        if not rules:
            return
        index = self.cfg["settings"].get("double_tap_rule", 0)
        chosen = self.cfg["rules"][index] if 0 <= index < len(self.cfg["rules"]) else None
        rule = chosen if any(chosen is r for r in rules) else rules[0]
        threading.Thread(target=self._run, args=(rule, tr("dtap_title")), daemon=True).start()

    def _run(self, rule, prefix=""):
        def change(text):
            result, src, dst = self.convert(rule, text)
            message = tr("converted").format(a=lang_name(src), b=lang_name(dst))
            return result, (prefix + " | " + message) if prefix else message

        self._process(change, rtl_first=LANGUAGES[rule["src"]]["script"] in RTL_SCRIPTS)

    def _change_case(self):
        def change(text):
            last = self._last_case
            forced = False
            # Some programs (Chrome's address bar) rewrite the case of what they copy, e.g. a link.
            # If the copied text is the one we produced a moment ago, continue from our own copy.
            if last and time.time() - last["time"] < 120 and text != last["text"] \
                    and text.lower() == last["text"].lower():
                text, forced = last["text"], True
            result, state = cycle_case(text)
            self._last_case = {"text": result, "time": time.time()}
            return result, tr("case_" + state), forced

        self._process(change, reselect=True)

    def _acquire(self):
        """Take the one-at-a-time lock. A worker stuck for 20 s is abandoned, so it can never block everything."""
        if self._lock.acquire(blocking=False):
            self._busy_since = time.time()
            return self._lock
        if time.time() - self._busy_since > STALE_LOCK:
            self._lock = threading.Lock()
            self._lock.acquire()
            self._busy_since = time.time()
            return self._lock
        return None

    # ------------------------------------------------------- keys we send
    def _copy_keys(self):
        return [winapi.VK_LCTRL, winapi.VK_C]

    def _paste_keys(self):
        return [winapi.VK_LCTRL, winapi.VK_V]

    def _read_selection(self):
        # Some apps empty the clipboard first and fill it a moment later.
        for _ in range(25):
            text = winapi.get_clipboard_text()
            if text:
                return text
            time.sleep(0.004)
        return ""

    def _copy_once(self, timeout):
        seq = winapi.clipboard_seq()
        winapi.send_combo(*self._copy_keys())
        return winapi.wait_clipboard_change(seq, timeout)

    def _copy_selection(self, rtl_first):
        """Copy the selection; with nothing selected, select the last word and copy that."""
        copied = self._copy_once(0.30)
        if not copied and self.cfg["settings"].get("convert_last_word", True):
            # Right-to-left text (Arabic) moves the caret the other way, so try both.
            arrows = ((winapi.VK_RIGHT, winapi.VK_LEFT) if rtl_first
                      else (winapi.VK_LEFT, winapi.VK_RIGHT))
            for arrow in arrows:
                winapi.send_combo(winapi.VK_LCTRL, winapi.VK_LSHIFT, arrow)
                time.sleep(0.01)
                copied = self._copy_once(0.20)
                if copied:
                    break
        return copied

    def _blocked(self):
        return {x.strip().lower() for x in self.cfg["settings"].get("excluded_apps", [])}

    # ----------------------------------------------------------- the main flow
    def _process(self, change, rtl_first=False, reselect=False):
        """change(text) -> (new_text, message). Replaces the selection (or last word)."""
        lock = self._acquire()
        if not lock:
            return
        old = None
        try:
            settings = self.cfg["settings"]
            process = winapi.foreground_process_name()
            if process in self._blocked():
                return
            if process in OWN_PROCESSES and not self.practice:
                self.notify(tr("own_window"), False)  # the Keyboard Flip window itself has nothing to convert
                return
            hwnd = winapi.foreground_window()

            winapi.release_modifiers()
            old = winapi.get_clipboard_text()
            copied = self._copy_selection(rtl_first)
            text = self._read_selection() if copied else ""
            if not text:
                # Windows hides the name of programs running as Administrator and
                # also blocks us from sending them keys: tell the user why.
                self.notify(tr("nothing") if process else tr("admin_app"), False)
                return

            try:
                out = change(text)
                result, message = out[0], out[1]
                forced = len(out) > 2 and out[2]
            except Exception:
                self.notify(tr("layout_missing"), False)
                return
            if result == text and not forced:
                self.notify(tr("unchanged"), False)
                return
            if settings.get("preview") and not self._confirm(hwnd, message, result):
                self.notify(tr("cancelled"), False)
                return

            winapi.set_clipboard_text(result)
            winapi.send_combo(*self._paste_keys())
            self._remember(message, text, result)
            self.notify(message, True)
            time.sleep(0.12)  # let the target app read the clipboard before we restore it
            if reselect:
                self._reselect(result)
        except Exception:
            _log_error()
        finally:
            self._restore_clipboard(old)
            lock.release()

    @staticmethod
    def _restore_clipboard(old):
        try:
            if old:
                winapi.set_clipboard_text(old)
        except Exception:
            _log_error()

    def _confirm(self, hwnd, message, result):
        """Show the result in a small box and wait for Enter (True) or Esc (False)."""
        if not self.request:
            return True
        done, answer = threading.Event(), {"ok": False}

        def decide(ok):
            answer["ok"] = bool(ok)
            done.set()

        self.request("preview", message, result, decide)
        if not done.wait(PREVIEW_TIMEOUT + 2) or not answer["ok"]:
            return False
        winapi.focus_window(hwnd)  # the box took the focus; give it back before pasting
        time.sleep(0.10)
        return True

    def _reselect(self, text):
        """Select the text we just pasted again, so the shortcut can be pressed once more."""
        if not self.cfg["settings"].get("case_reselect", True):
            return
        steps = len(re.sub(r"\r\n|\r|\n", "\n", text))  # a line break is one caret step
        if not 0 < steps <= RESELECT_MAX:
            return
        events = [(winapi.VK_LSHIFT, True)]
        for _ in range(steps):
            events += [(winapi.VK_LEFT, True), (winapi.VK_LEFT, False)]
        events.append((winapi.VK_LSHIFT, False))
        winapi.send_keys(events)

    def _remember(self, message, before, after, history=True):
        """Keep the change for Undo, and (if switched on) for the History tab."""
        self.undo_stack.append({"time": time.time(), "proc": winapi.foreground_process_name()})
        if history and self.cfg["settings"].get("history", True):
            self.history.appendleft({"time": time.time(), "message": message,
                                     "before": before, "after": after})
            self.save_history()
            if self.request:
                self.request("history")

    def save_history(self):
        """Keep the history in a file while the program runs. main.py deletes it at quit and at start."""
        try:
            if not self.history or not self.cfg["settings"].get("history", True):
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                return
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = HISTORY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, ensure_ascii=False)
            os.replace(tmp, HISTORY_FILE)
        except Exception:
            _log_error()

    def clear_history(self):
        self.history.clear()
        self.save_history()

    # --------------------------------------------------------------- snippets
    def _open_snippets(self):
        if winapi.foreground_process_name() in self._blocked() or not self.request:
            return
        self.request("snippets", winapi.foreground_window())

    def paste_snippet(self, hwnd, text):
        """Paste `text` into the window that had the focus before the menu opened."""
        threading.Thread(target=self._paste_snippet, args=(hwnd, text), daemon=True).start()

    def _paste_snippet(self, hwnd, text):
        lock = self._acquire()
        if not lock:
            return
        old = None
        try:
            old = winapi.get_clipboard_text()
            winapi.focus_window(hwnd)
            time.sleep(0.12)
            winapi.set_clipboard_text(text)
            winapi.send_combo(*self._paste_keys())
            self._remember("", "", "", history=False)
            time.sleep(0.15)
        except Exception:
            _log_error()
        finally:
            self._restore_clipboard(old)
            lock.release()

    # ------------------------------------------------------------------- undo
    def _undo(self):
        """Undo = Ctrl+Z in the same program. Each press goes one change further back."""
        lock = self._acquire()
        if not lock:
            return
        try:
            stack = self.undo_stack
            if stack and time.time() - stack[-1]["time"] > UNDO_WINDOW:
                stack.clear()
            if not stack or winapi.foreground_process_name() != stack[-1]["proc"]:
                self.notify(tr("nothing_to_undo"), False)
                return
            winapi.release_modifiers()
            winapi.send_combo(winapi.VK_LCTRL, winapi.VK_Z)
            stack.pop()
            self.notify(tr("undone"), True)
        except Exception:
            _log_error()
        finally:
            lock.release()
