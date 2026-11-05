"""Tests for the 1.1 features that don't need Windows."""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from keyboardflip import config, i18n, layouts as L, updates, winapi  # noqa: E402
from keyboardflip.locales import ar, de, en, es, fr, ru  # noqa: E402
from keyboardflip.textcase import cycle_case, sentence_case  # noqa: E402

LOCALES = {"ar": ar, "de": de, "es": es, "fr": fr, "ru": ru}


class CaseCycle(unittest.TestCase):
    def walk(self, text, steps=4):
        out = []
        for _ in range(steps):
            text, state = cycle_case(text)
            out.append((text, state))
        return out

    def test_lower_goes_upper_sentence_lower(self):
        self.assertEqual(self.walk("hello world", 3), [
            ("HELLO WORLD", "upper"), ("Hello world", "sentence"), ("hello world", "lower")])

    def test_it_loops(self):
        self.assertEqual(self.walk("hello world", 4)[3], ("HELLO WORLD", "upper"))

    def test_mixed_case_starts_with_upper(self):
        self.assertEqual(cycle_case("MiXed CaSe")[0], "MIXED CASE")

    def test_sentences(self):
        self.assertEqual(sentence_case("hELLO. hOW are YOU? fine"), "Hello. How are you? Fine")
        self.assertEqual(sentence_case("1. first item"), "1. First item")

    def test_single_letter_still_changes(self):
        self.assertEqual(cycle_case("A")[0], "a")

    def test_text_without_case_is_unchanged(self):
        self.assertEqual(cycle_case("123")[0], "123")
        self.assertEqual(cycle_case("مرحبا")[0], "مرحبا")


class Languages(unittest.TestCase):
    def test_new_languages_are_registered(self):
        for code in ("tr", "uk", "fa", "hi", "ur", "it", "pt", "el"):
            self.assertIn(code, L.LANGUAGES)
            self.assertIn(code, L.DEFAULT_LAYOUTS)
            self.assertIn(code, en.LANG_NAMES)
            for layout_id in L.LANGUAGES[code]["layouts"]:
                self.assertEqual(L.LAYOUT_INFO[layout_id][2], code)

    def test_only_the_original_six_are_on_by_default(self):
        self.assertEqual(config.DEFAULT_CONFIG["languages"], ["en", "ar", "de", "fr", "es", "ru"])

    def test_every_script_is_counted(self):
        scripts = {info["script"] for info in L.LANGUAGES.values()}
        counts = L.script_counts("abc नमस्ते γειά привет مرحبا")
        self.assertTrue(scripts <= set(counts))
        self.assertTrue(all(counts[s] > 0 for s in ("latin", "devanagari", "greek", "cyrillic", "arabic")))

    def test_hebrew_is_gone_and_urdu_is_right_to_left(self):
        self.assertNotIn("he", L.LANGUAGES)
        self.assertIn(L.LANGUAGES["ur"]["script"], L.RTL_SCRIPTS)
        self.assertNotIn(L.LANGUAGES["hi"]["script"], L.RTL_SCRIPTS)

    def test_only_arabic_interface_is_right_to_left(self):
        from keyboardflip import i18n
        for code, expected in (("ar", True), ("en", False), ("de", False)):
            i18n.set_language(code)
            self.assertEqual(i18n.is_rtl(), expected)
        i18n.set_language("en")


class Locales(unittest.TestCase):
    def test_every_language_has_every_key(self):
        for code, mod in LOCALES.items():
            self.assertEqual(set(mod.STRINGS), set(en.STRINGS), code)
            self.assertEqual(set(mod.LANG_NAMES), set(en.LANG_NAMES), code)

    def test_placeholders_match_english(self):
        fields = lambda text: sorted(re.findall(r"\{(\w+)\}", text))  # noqa: E731
        for code, mod in LOCALES.items():
            for key, text in en.STRINGS.items():
                self.assertEqual(fields(mod.STRINGS[key]), fields(text), "%s/%s" % (code, key))

    def test_tr_falls_back_to_english(self):
        i18n.set_language("zz")
        self.assertEqual(i18n.tr("tab_rules"), "Conversions")
        self.assertEqual(i18n.tr("no_such_key"), "no_such_key")
        i18n.set_language("en")

    def test_theme_and_accent_names_exist(self):
        for theme in config.THEMES:
            self.assertIn("theme_" + theme, en.STRINGS)
        for accent in config.ACCENTS:
            self.assertIn("accent_" + accent, en.STRINGS)


class Config(unittest.TestCase):
    def test_snippets_are_cleaned(self):
        clean = config._clean_snippets([
            {"title": " Email ", "text": "me@x.com"}, {"title": "", "text": "x"},
            {"title": "t", "text": ""}, "junk", {"title": 1, "text": "x"}])
        self.assertEqual(clean, [{"title": "Email", "text": "me@x.com"}])

    def test_defaults_keep_privacy_features_off(self):
        st = config.DEFAULT_CONFIG["settings"]
        self.assertFalse(st["check_updates"])
        self.assertFalse(st["preview"])
        self.assertEqual(st["double_tap_key"], "off")

    def test_version_is_the_same_everywhere(self):
        with open(os.path.join(ROOT, "installer.iss"), encoding="utf-8") as f:
            installer = re.search(r'#define AppVersion "([^"]+)"', f.read()).group(1)
        self.assertEqual(installer, config.VERSION)


class Keys(unittest.TestCase):
    def test_combo_vks(self):
        self.assertEqual(winapi.combo_vks("ctrl+C"), [winapi.VK_LCTRL, winapi.VK_C])
        self.assertEqual(winapi.combo_vks("ctrl+shift+V"), [winapi.VK_LCTRL, winapi.VK_LSHIFT, winapi.VK_V])
        self.assertEqual(winapi.combo_vks("shift+insert"), [winapi.VK_LSHIFT, 0x2D])
        self.assertIsNone(winapi.combo_vks("ctrl+nope"))
        self.assertIsNone(winapi.combo_vks(""))


class Updates(unittest.TestCase):
    def test_version_compare(self):
        self.assertTrue(updates.is_newer("v1.2.0", "1.1.0"))
        self.assertTrue(updates.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(updates.is_newer("1.1.0", "1.1.0"))
        self.assertFalse(updates.is_newer("1.0.9", "1.1.0"))
        self.assertFalse(updates.is_newer("garbage", "1.1.0"))


if __name__ == "__main__":
    unittest.main()


class DoubleTapAndCase(unittest.TestCase):
    def test_double_tap_fires_on_two_quick_taps_only(self):
        import time
        from unittest import mock
        from keyboardflip import winapi

        down = set()

        class FakeUser32:
            @staticmethod
            def GetAsyncKeyState(vk):
                return 0x8000 if vk in down else 0

        hits = []
        listener = winapi.DoubleTapListener(lambda: hits.append(1))

        def tap(vk=0x10, hold=0.05, extra=None):
            down.add(vk); down.add(0xA0)
            if extra:
                down.add(extra)
            time.sleep(hold)
            down.clear()

        with mock.patch.object(winapi, "IS_WIN", True), mock.patch.object(winapi, "user32", FakeUser32, create=True):
            listener.start("shift")
            time.sleep(0.1)
            tap(); time.sleep(0.12); tap()
            time.sleep(0.2)
            self.assertEqual(len(hits), 1)
            tap(); time.sleep(1.0); tap()          # too slow: no conversion
            time.sleep(0.2)
            self.assertEqual(len(hits), 1)
            tap(extra=0x41); time.sleep(0.1); tap()  # Shift+A is typing, not a tap
            time.sleep(0.2)
            self.assertEqual(len(hits), 1)
            listener.stop()

    def test_case_cycle_survives_a_program_that_rewrites_copied_links(self):
        from test_engine import FakeWindows, make_engine
        engine, cfg, _ = make_engine()
        cfg["settings"]["case_reselect"] = False
        url = "https://claude.ai/chat/7d6fab69-8402"
        win = FakeWindows(url)
        seen = []
        for _ in range(3):
            with win.patch():
                engine._change_case()
            seen.append(win.selection)
            # the "browser" gives the link back in its own normalised form (scheme and host in lower case)
            win.selection = win.selection.replace("HTTPS://CLAUDE.AI", "https://claude.ai")
            win.selection = win.selection.replace("Https://claude.Ai", "https://claude.ai")
        self.assertEqual(seen[0], url.upper())
        self.assertTrue(seen[1].startswith("Https://"))
        self.assertEqual(seen[2], url)


class TapTrackerTests(unittest.TestCase):
    def run_keys(self, events):
        hits = []
        tracker = winapi.TapTracker((0xA0, 0xA1), lambda: hits.append(1))
        for vk, down, t in events:
            tracker.key(vk, down, t)
        return len(hits)

    def test_two_quick_taps(self):
        self.assertEqual(self.run_keys([(0xA0, True, 0), (0xA0, False, .06), (0xA0, True, .2), (0xA0, False, .26)]), 1)

    def test_key_repeat_while_held_is_one_press(self):
        self.assertEqual(self.run_keys([(0xA0, True, 0), (0xA0, True, .03), (0xA0, False, .06),
                                        (0xA0, True, .2), (0xA0, True, .22), (0xA0, False, .26)]), 1)

    def test_too_slow_or_typing_does_not_count(self):
        self.assertEqual(self.run_keys([(0xA0, True, 0), (0xA0, False, .06), (0xA0, True, 1.5), (0xA0, False, 1.56)]), 0)
        self.assertEqual(self.run_keys([(0xA0, True, 0), (0x41, True, .02), (0xA0, False, .06),
                                        (0xA0, True, .2), (0xA0, False, .26)]), 0)
        self.assertEqual(self.run_keys([(0xA0, True, 0), (0xA0, False, .06), (0x41, True, .1), (0x41, False, .12),
                                        (0xA0, True, .2), (0xA0, False, .26)]), 0)
