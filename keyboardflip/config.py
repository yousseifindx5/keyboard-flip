import copy
import json
import os

from .layouts import DEFAULT_LANGUAGES, DEFAULT_LAYOUTS, LANGUAGES

APP_NAME = "Keyboard Flip"
VERSION = "1.1.0"
REPO = "yousseifindx5/keyboard-flip"
RELEASES_URL = "https://github.com/%s/releases/latest" % REPO
MAX_RULES = 10
MAX_SNIPPETS = 30
SNIPPET_TITLE_MAX = 60
SNIPPET_TEXT_MAX = 5000
CONFIG_VERSION = 2

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KeyboardFlip")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LANG_CODES = tuple(LANGUAGES)
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")  # exists only while the program runs

THEMES = ("System", "Light", "Dark", "Midnight", "Sand")
ACCENTS = ("Blue", "Green", "Purple", "Orange", "Rose", "Teal")
DOUBLE_TAP_KEYS = ("off", "shift", "ctrl")

DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "languages": list(DEFAULT_LANGUAGES),
    "layouts": dict(DEFAULT_LAYOUTS),
    "rules": [
        {"src": "en", "dst": "ar", "hotkey": "ctrl+alt+L", "enabled": True, "bidirectional": False},
        {"src": "ar", "dst": "en", "hotkey": "ctrl+alt+K", "enabled": True, "bidirectional": False},
    ],
    # Text you paste from the snippets menu: [{"title": "Email", "text": "me@example.com"}]
    "snippets": [],
    "settings": {
        "enabled": True,
        "autostart": False,
        "notify": True,
        "convert_last_word": True,
        "undo_hotkey": "ctrl+alt+Z",
        "case_hotkey": "ctrl+alt+U",
        "case_reselect": True,
        "snippets_hotkey": "ctrl+alt+S",
        "preview": False,
        "history": True,
        "double_tap_key": "off",
        "double_tap_rule": 0,
        "excluded_apps": ["cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "conhost.exe"],
        "ui_language": "en",
        "theme": "System",
        "accent": "Blue",
        "check_updates": False,
        "last_update_check": 0.0,
        "onboarded": False,
    },
}


def _clean_snippets(items):
    clean = []
    if not isinstance(items, list):
        return clean
    for item in items[:MAX_SNIPPETS]:
        if not isinstance(item, dict):
            continue
        title, text = item.get("title"), item.get("text")
        if isinstance(title, str) and isinstance(text, str) and title.strip() and text:
            clean.append({"title": title.strip()[:SNIPPET_TITLE_MAX], "text": text[:SNIPPET_TEXT_MAX]})
    return clean


def load_config():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return cfg
    if not isinstance(data, dict):
        return cfg

    langs = data.get("languages")
    if isinstance(langs, list) and data.get("version", 1) >= CONFIG_VERSION:
        langs = [c for c in LANG_CODES if c in langs]
        if len(langs) >= 2:
            cfg["languages"] = langs

    layouts = data.get("layouts")
    if isinstance(layouts, dict):
        for code, layout_id in layouts.items():
            if code in cfg["layouts"] and layout_id in LANGUAGES[code]["layouts"]:
                cfg["layouts"][code] = layout_id

    rules = data.get("rules")
    if isinstance(rules, list):
        clean = []
        for r in rules[:MAX_RULES]:
            if (isinstance(r, dict) and r.get("src") in LANG_CODES and r.get("dst") in LANG_CODES
                    and isinstance(r.get("hotkey"), str)):
                clean.append({
                    "src": r["src"], "dst": r["dst"], "hotkey": r["hotkey"],
                    "enabled": bool(r.get("enabled", True)),
                    "bidirectional": bool(r.get("bidirectional", False)),
                })
        cfg["rules"] = clean

    cfg["snippets"] = _clean_snippets(data.get("snippets"))

    settings = data.get("settings")
    if isinstance(settings, dict):
        for key, value in settings.items():
            if key in cfg["settings"] and type(value) is type(cfg["settings"][key]):
                cfg["settings"][key] = value
        st = cfg["settings"]
        apps = st["excluded_apps"]
        st["excluded_apps"] = [a.strip().lower() for a in apps if isinstance(a, str) and a.strip()]
        if st["theme"] not in THEMES:
            st["theme"] = "System"
        if st["accent"] not in ACCENTS:
            st["accent"] = "Blue"
        if st["double_tap_key"] not in DOUBLE_TAP_KEYS:
            st["double_tap_key"] = "off"
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except Exception:
        pass


def delete_history_file():
    """The history is deleted whenever the program is not running (at quit, and at the next start)."""
    try:
        os.remove(HISTORY_FILE)
    except OSError:
        pass
