"""Runs the engine against a fake Windows (clipboard + keys), so the logic is tested anywhere."""
import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keyboardflip import config, winapi  # noqa: E402
from keyboardflip import engine as engine_module  # noqa: E402
from keyboardflip.engine import Engine  # noqa: E402
import tempfile  # noqa: E402

_TMP = tempfile.mkdtemp()  # the history file goes here, never into the real settings folder
engine_module.CONFIG_DIR = _TMP
engine_module.HISTORY_FILE = os.path.join(_TMP, "history.json")


class FakeWindows:
    """A tiny text box: `selection` is what is selected, `clipboard` the clipboard."""

    def __init__(self, selection, clipboard="old clipboard"):
        self.selection, self.clipboard, self.seq = selection, clipboard, 0
        self.sent, self.events, self.undone = [], [], 0

    def send_combo(self, *vks):
        self.sent.append(list(vks))
        if list(vks) == [winapi.VK_LCTRL, winapi.VK_C] or list(vks) == [0xA2, 0x2D]:
            if self.selection:
                self.clipboard, self.seq = self.selection, self.seq + 1
        elif list(vks) == [winapi.VK_LCTRL, winapi.VK_V] or list(vks) == [0xA0, 0x2D]:
            self.selection = self.clipboard
        elif list(vks) == [winapi.VK_LCTRL, winapi.VK_Z]:
            self.undone += 1

    def set_clipboard_text(self, text):
        self.clipboard, self.seq = text, self.seq + 1
        return True

    def patch(self):
        names = dict(
            send_combo=self.send_combo, set_clipboard_text=self.set_clipboard_text,
            get_clipboard_text=lambda: self.clipboard, clipboard_seq=lambda: self.seq,
            wait_clipboard_change=lambda seq, timeout: self.seq != seq,
            foreground_process_name=lambda: "notepad.exe", foreground_window=lambda: 1,
            release_modifiers=lambda: None, focus_window=lambda hwnd: None,
            send_keys=lambda events: self.events.append(list(events)))
        return mock.patch.multiple(winapi, **names)


def make_engine():
    cfg = copy.deepcopy(config.DEFAULT_CONFIG)
    toasts = []
    engine = Engine(cfg, lambda text, ok=True: toasts.append((text, ok)))
    return engine, cfg, toasts


class EngineFlow(unittest.TestCase):
    def test_convert_replaces_selection_and_restores_clipboard(self):
        engine, cfg, toasts = make_engine()
        win = FakeWindows("hello")
        with win.patch():
            engine._run(cfg["rules"][0])
        self.assertEqual(win.selection, "اثممخ")
        self.assertEqual(win.clipboard, "old clipboard")
        self.assertEqual(len(engine.history), 1)
        self.assertEqual(engine.history[0]["before"], "hello")
        self.assertTrue(toasts[-1][1])

    def test_history_can_be_turned_off(self):
        engine, cfg, _ = make_engine()
        cfg["settings"]["history"] = False
        win = FakeWindows("hello")
        with win.patch():
            engine._run(cfg["rules"][0])
        self.assertEqual(len(engine.history), 0)
        self.assertEqual(len(engine.undo_stack), 1)  # undo still works

    def test_case_cycles_and_selects_the_text_again(self):
        engine, cfg, _ = make_engine()
        win = FakeWindows("hello world")
        with win.patch():
            engine._change_case()
            self.assertEqual(win.selection, "HELLO WORLD")
            self.assertEqual(len(win.events), 1)
            self.assertEqual(len(win.events[0]), 2 * len("HELLO WORLD") + 2)
            engine._change_case()
            self.assertEqual(win.selection, "Hello world")
            engine._change_case()
            self.assertEqual(win.selection, "hello world")

    def test_reselect_can_be_turned_off(self):
        engine, cfg, _ = make_engine()
        cfg["settings"]["case_reselect"] = False
        win = FakeWindows("hello")
        with win.patch():
            engine._change_case()
        self.assertEqual(win.events, [])

    def test_undo_goes_back_one_change_at_a_time(self):
        engine, cfg, toasts = make_engine()
        win = FakeWindows("hello")
        with win.patch():
            engine._run(cfg["rules"][0])  # hello -> Arabic
            engine._run(cfg["rules"][1])  # Arabic -> hello
            engine._undo()
            engine._undo()
            engine._undo()  # nothing left
        self.assertEqual(win.undone, 2)
        self.assertFalse(toasts[-1][1])

    def test_undo_stack_is_limited_to_ten(self):
        engine, cfg, _ = make_engine()
        with FakeWindows("x").patch():
            for _ in range(15):
                engine._remember("m", "a", "b")
        self.assertEqual(len(engine.undo_stack), 10)

    def test_preview_can_cancel_or_apply(self):
        for answer, expected in ((False, "hello"), (True, "اثممخ")):
            engine, cfg, _ = make_engine()
            cfg["settings"]["preview"] = True
            engine.request = lambda kind, *args, a=answer: args[-1](a) if kind == "preview" else None
            win = FakeWindows("hello")
            with win.patch():
                engine._run(cfg["rules"][0])
            self.assertEqual(win.selection, expected)

    def test_own_window_gets_a_clear_message(self):
        engine, cfg, toasts = make_engine()
        win = FakeWindows("hello")
        with win.patch(), mock.patch.object(winapi, "foreground_process_name", lambda: "keyboardflip.exe"):
            engine._run(cfg["rules"][0])
            self.assertEqual(win.selection, "hello")
            engine.practice = True
            engine._run(cfg["rules"][0])
        self.assertEqual(win.selection, "اثممخ")
        self.assertFalse(toasts[0][1])

    def test_a_stuck_worker_cannot_block_forever(self):
        engine, cfg, _ = make_engine()
        engine._lock.acquire()
        engine._busy_since = 0.0  # stuck since long ago
        win = FakeWindows("hello")
        with win.patch():
            engine._run(cfg["rules"][0])
        self.assertEqual(win.selection, "اثممخ")

    def test_history_file_follows_history(self):
        engine, cfg, _ = make_engine()
        win = FakeWindows("hello")
        with win.patch():
            engine._run(cfg["rules"][0])
        self.assertTrue(os.path.exists(engine_module.HISTORY_FILE))
        engine.clear_history()
        self.assertFalse(os.path.exists(engine_module.HISTORY_FILE))
        with win.patch():
            engine._run(cfg["rules"][0])
        config.HISTORY_FILE, old = engine_module.HISTORY_FILE, config.HISTORY_FILE
        config.delete_history_file()
        config.HISTORY_FILE = old
        self.assertFalse(os.path.exists(engine_module.HISTORY_FILE))

    def test_snippet_is_pasted_and_clipboard_restored(self):
        engine, cfg, _ = make_engine()
        win = FakeWindows("", clipboard="keep me")
        with win.patch():
            engine._paste_snippet(1, "me@example.com")
        self.assertEqual(win.selection, "me@example.com")
        self.assertEqual(win.clipboard, "keep me")
        self.assertEqual(len(engine.history), 0)  # snippets never go to the history

    def test_double_tap_uses_the_chosen_conversion(self):
        engine, cfg, _ = make_engine()
        cfg["settings"]["double_tap_rule"] = 1
        win = FakeWindows("اثممخ")
        with win.patch(), mock.patch("keyboardflip.engine.threading.Thread") as thread:
            engine._on_double_tap()
        self.assertIs(thread.call_args.kwargs["args"][0], cfg["rules"][1])


if __name__ == "__main__":
    unittest.main()
