"""Tests for the parts that don't need Windows. Run:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keyboardflip import config, layouts as L, winapi  # noqa: E402


def conv(text, src, dst):
    return L.convert_between(text, src, dst)


class LayoutTables(unittest.TestCase):
    def test_every_static_layout_has_48_slots(self):
        for layout_id in L.STATIC:
            lay = L.get_layout(layout_id)
            self.assertEqual(len(lay["normal"]), L.SLOTS, layout_id)
            self.assertEqual(len(lay["shift"]), L.SLOTS, layout_id)

    def test_every_language_layout_is_known(self):
        for code, info in L.LANGUAGES.items():
            for layout_id in info["layouts"]:
                self.assertEqual(L.LAYOUT_INFO[layout_id][2], code)
        for code, layout_id in L.DEFAULT_LAYOUTS.items():
            self.assertIn(layout_id, L.LANGUAGES[code]["layouts"])


class Conversion(unittest.TestCase):
    def test_english_arabic(self):
        self.assertEqual(conv("hello", "en-US", "ar-101"), "اثممخ")
        self.assertEqual(conv("اثممخ", "ar-101", "en-US"), "hello")
        self.assertEqual(conv("sghl", "en-US", "ar-101"), "سلام")

    def test_other_layouts(self):
        self.assertEqual(conv("ghbdtn", "en-US", "ru"), "привет")
        self.assertEqual(conv("привет", "ru", "en-US"), "ghbdtn")
        self.assertEqual(conv("qwerty", "en-US", "fr-FR"), "azerty")
        self.assertEqual(conv("yes", "en-US", "de-DE"), "zes")
        self.assertEqual(conv(";", "en-US", "es-ES"), "ñ")

    def test_capital_letters_survive_a_round_trip(self):
        # Shift+D, F, C, V, Z, L on the Arabic layout type ] [ } { ~ /
        text = "Dad Fox Cat Van Zoo Lol Hello"
        self.assertEqual(conv(conv(text, "en-US", "ar-101"), "ar-101", "en-US"), text)

    def test_real_symbols_in_numbers_and_ascii_words_are_left_alone(self):
        self.assertEqual(conv("اثممخ 2026/11/03 [x] وصل", "ar-101", "en-US"), "hello 2026/11/03 [x] ,wg")

    def test_lam_alef_prefers_the_more_english_reading(self):
        for word in ("right", "light", "about", "global", "enough", "before", "bob", "table"):
            self.assertEqual(conv(conv(word, "en-US", "ar-101"), "ar-101", "en-US"), word)

    def test_unknown_characters_pass_through(self):
        self.assertEqual(conv("hello 123 ☺", "en-US", "ar-101"), "اثممخ 123 ☺")


class Hotkeys(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(winapi.normalize_hotkey("alt+CTRL+l"), "ctrl+alt+L")
        self.assertEqual(winapi.normalize_hotkey("f8"), "F8")

    def test_invalid(self):
        for bad in ("", "ctrl+alt+", "ctrl+nope", "ctrl+a+b"):
            self.assertEqual(winapi.normalize_hotkey(bad), "", bad)

    def test_default_config_hotkeys_are_valid_and_unique(self):
        keys = [winapi.normalize_hotkey(r["hotkey"]) for r in config.DEFAULT_CONFIG["rules"]]
        for name in ("undo_hotkey", "case_hotkey", "snippets_hotkey"):
            keys.append(winapi.normalize_hotkey(config.DEFAULT_CONFIG["settings"][name]))
        self.assertNotIn("", keys)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertLessEqual(len(config.DEFAULT_CONFIG["rules"]), config.MAX_RULES)


if __name__ == "__main__":
    unittest.main()
