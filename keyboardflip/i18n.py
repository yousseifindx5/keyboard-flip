"""Interface strings. The texts live in keyboardflip/locales/<code>.py (one file per language)."""
from .locales import ar, de, en, es, fr, ru

# code -> (name shown in the language list, module). To add a language, add one line here.
_LOCALES = {
    "en": ("English", en),
    "ar": ("العربية", ar),
    "de": ("Deutsch", de),
    "fr": ("Français", fr),
    "es": ("Español", es),
    "ru": ("Русский", ru),
}
UI_LANGUAGES = {code: name for code, (name, _) in _LOCALES.items()}

_RTL = {"ar"}  # interface languages written right to left
_lang = "en"


def set_language(code):
    global _lang
    _lang = code if code in _LOCALES else "en"


def get_language():
    return _lang


def tr(key):
    """The text for `key` in the current language (English if it is missing there)."""
    return _LOCALES[_lang][1].STRINGS.get(key) or en.STRINGS.get(key, key)


def lang_name(code):
    """Name of a keyboard language (e.g. "ar") written in the current interface language."""
    return _LOCALES[_lang][1].LANG_NAMES.get(code) or en.LANG_NAMES.get(code, code)


def is_rtl():
    """True when the interface language is written right to left (the whole window is mirrored)."""
    return _lang in _RTL
