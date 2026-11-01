import copy
import json
import os

from .layouts import DEFAULT_LAYOUTS, LANGUAGES

APP_NAME = "Keyboard Flip"
VERSION = "1.0.0"
MAX_RULES = 10
CONFIG_VERSION = 2

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KeyboardFlip")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LANG_CODES = tuple(LANGUAGES)

DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "languages": list(LANGUAGES),
    "layouts": dict(DEFAULT_LAYOUTS),
    "rules": [
        {"src": "en", "dst": "ar", "hotkey": "ctrl+alt+L", "enabled": True, "bidirectional": False},
        {"src": "ar", "dst": "en", "hotkey": "ctrl+alt+K", "enabled": True, "bidirectional": False},
    ],
    "settings": {
        "enabled": True,
        "autostart": False,
        "notify": True,
        "convert_last_word": True,
        "undo_hotkey": "ctrl+alt+Z",
        "excluded_apps": ["cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "conhost.exe"],
        "ui_language": "en",
        "theme": "System",
    },
}


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

    settings = data.get("settings")
    if isinstance(settings, dict):
        for key, value in settings.items():
            if key in cfg["settings"] and type(value) is type(cfg["settings"][key]):
                cfg["settings"][key] = value
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
