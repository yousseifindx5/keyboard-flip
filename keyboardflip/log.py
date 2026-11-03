"""Writes unexpected errors to %APPDATA%\\KeyboardFlip\\error.log (the windowed exe has no console)."""
import os
import time
import traceback

from .config import CONFIG_DIR


def log_error(text=None):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + (text or traceback.format_exc()) + "\n")
    except Exception:
        pass
