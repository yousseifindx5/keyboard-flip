"""The conversion engine: hotkey -> copy selection -> convert -> paste."""
import os
import threading
import time
import traceback

from . import winapi
from .config import CONFIG_DIR
from .i18n import lang_name, tr
from .layouts import DEFAULT_LAYOUTS, LANGUAGES, convert_between, script_counts


def _log_error():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
    except Exception:
        pass


UNDO_ID = 1000
UNDO_WINDOW = 30  # seconds after a conversion during which Undo is allowed


class Engine:
    def __init__(self, cfg, notify):
        """notify(text, ok) is called from worker threads; it must be thread-safe."""
        self.cfg = cfg
        self.notify = notify
        self.listener = winapi.HotkeyListener(self._on_hotkey)
        self.bindings = {}
        self.failed = []
        self.active = 0
        self._lock = threading.Lock()
        self.last = None  # {'time', 'proc'} of the last successful conversion

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
        self.bindings, self.failed, self.active = {}, [], 0
        if not self.cfg["settings"].get("enabled", True):
            return []
        items = []
        for n, rule in enumerate(self._valid_rules(), start=1):
            self.bindings[n] = rule
            items.append((n, rule["hotkey"]))
        rule_keys = {winapi.normalize_hotkey(hk) for _, hk in items}
        undo = self.cfg["settings"].get("undo_hotkey", "")
        undo_key = winapi.normalize_hotkey(undo) if undo else ""
        all_items = list(items)
        if undo_key and undo_key not in rule_keys:
            all_items.append((UNDO_ID, undo))
        self.listener.start(all_items)
        self.failed = list(self.listener.failed)
        self.active = sum(1 for _, hk in items if hk not in self.failed)
        return self.failed

    def suspend(self):
        self.listener.stop()

    def stop(self):
        self.listener.stop()

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

    def _on_hotkey(self, hid):
        if hid == UNDO_ID:
            threading.Thread(target=self._undo, daemon=True).start()
            return
        rule = self.bindings.get(hid)
        if rule:
            threading.Thread(target=self._run, args=(rule,), daemon=True).start()

    def _read_selection(self):
        # Some apps empty the clipboard first and fill it a moment later.
        for _ in range(25):
            text = winapi.get_clipboard_text()
            if text:
                return text
            time.sleep(0.004)
        return ""

    def _run(self, rule):
        if not self._lock.acquire(blocking=False):
            return
        old = None
        try:
            settings = self.cfg["settings"]
            blocked = {x.strip().lower() for x in settings.get("excluded_apps", [])}
            if winapi.foreground_process_name() in blocked:
                return

            winapi.release_modifiers()
            old = winapi.get_clipboard_text()

            seq = winapi.clipboard_seq()
            winapi.send_combo(winapi.VK_LCTRL, winapi.VK_C)
            copied = winapi.wait_clipboard_change(seq, 0.30)

            if not copied and settings.get("convert_last_word", True):
                # Right-to-left text (Arabic) moves the caret the other way, so try both.
                arrows = ((winapi.VK_RIGHT, winapi.VK_LEFT)
                          if LANGUAGES[rule["src"]]["script"] == "arabic"
                          else (winapi.VK_LEFT, winapi.VK_RIGHT))
                for arrow in arrows:
                    winapi.send_combo(winapi.VK_LCTRL, winapi.VK_LSHIFT, arrow)
                    time.sleep(0.01)
                    seq = winapi.clipboard_seq()
                    winapi.send_combo(winapi.VK_LCTRL, winapi.VK_C)
                    copied = winapi.wait_clipboard_change(seq, 0.20)
                    if copied:
                        break

            text = self._read_selection() if copied else ""
            if not text:
                self.notify(tr("nothing"), False)
                return

            try:
                result, src, dst = self.convert(rule, text)
            except Exception:
                self.notify(tr("layout_missing"), False)
                return
            if result == text:
                self.notify(tr("unchanged"), False)
                return

            winapi.set_clipboard_text(result)
            winapi.send_combo(winapi.VK_LCTRL, winapi.VK_V)
            self.last = {"time": time.time(), "proc": winapi.foreground_process_name()}
            self.notify(tr("converted").format(a=lang_name(src), b=lang_name(dst)), True)
            time.sleep(0.12)  # let the target app read the clipboard before we restore it
        except Exception:
            _log_error()
        finally:
            try:
                if old:
                    winapi.set_clipboard_text(old)
            except Exception:
                _log_error()
            self._lock.release()

    def _undo(self):
        """Undo = Ctrl+Z in the same program, shortly after a conversion."""
        if not self._lock.acquire(blocking=False):
            return
        try:
            last = self.last
            if (not last or time.time() - last["time"] > UNDO_WINDOW
                    or winapi.foreground_process_name() != last["proc"]):
                self.notify(tr("nothing_to_undo"), False)
                return
            winapi.release_modifiers()
            winapi.send_combo(winapi.VK_LCTRL, winapi.VK_Z)
            self.last = None
            self.notify(tr("undone"), True)
        except Exception:
            _log_error()
        finally:
            self._lock.release()
