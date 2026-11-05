"""Look and feel shared by the window and the popups: colours, small widgets, toast, shortcut recorder.

The colours are module variables. apply_palette() changes them, and every widget
created afterwards uses the new ones (the window rebuilds itself after a change).
"""
import tkinter as tk

import customtkinter as ctk

from . import winapi
from .i18n import is_rtl, tr
from .winapi import normalize_hotkey, vk_to_name

# ---------------------------------------------------------------------------
# Right-to-left support: in Arabic the whole window is mirrored. The code asks these
# helpers for sides / anchors / padding, and they flip them when the interface is RTL.
# ---------------------------------------------------------------------------
rtl = is_rtl
_FLIP = {"left": "right", "right": "left", "w": "e", "e": "w", "nw": "ne", "ne": "nw",
         "sw": "se", "se": "sw"}


def side(value):
    return _FLIP.get(value, value) if is_rtl() else value


def anchor(value):
    return _FLIP.get(value, value) if is_rtl() else value


def justify(value):
    return _FLIP.get(value, value) if is_rtl() else value


def pad(first, second):
    return (second, first) if is_rtl() else (first, second)


def sticky(value):
    return "".join(_FLIP.get(c, c) for c in value) if is_rtl() else value


def rgba(color):
    """'#rrggbb' -> (r, g, b, 255)"""
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


# ---------------------------------------------------------------------------
# Themes and accent colours
# ---------------------------------------------------------------------------
# (light, dark) pairs. "Midnight" and "Sand" force dark / light mode.
_NEUTRAL = {
    "default": dict(BG=("#e4e8ef", "#0f1115"), SIDEBAR=("#ffffff", "#15171c"),
                    CARD=("#ffffff", "#1a1d23"), BORDER=("#c3cbd8", "#2a2e36"),
                    TEXT=("#0b1220", "#f3f4f6"), MUTED=("#4b5563", "#9ca3af"),
                    KEYCAP=("#d9dfea", "#2b303a"), KEYCAP_HOVER=("#c7cfde", "#373d49"),
                    SWITCH_OFF=("#9aa4b5", "#3a3f4a")),
    "midnight": dict(BG=("#000000", "#000000"), SIDEBAR=("#07080a", "#07080a"),
                     CARD=("#0d0f12", "#0d0f12"), BORDER=("#20242b", "#20242b"),
                     TEXT=("#f3f4f6", "#f3f4f6"), MUTED=("#9ca3af", "#9ca3af"),
                     KEYCAP=("#1b1f27", "#1b1f27"), KEYCAP_HOVER=("#2a303b", "#2a303b"),
                     SWITCH_OFF=("#3a3f4a", "#3a3f4a")),
    "sand": dict(BG=("#f1e9db", "#f1e9db"), SIDEBAR=("#fbf7ef", "#fbf7ef"),
                 CARD=("#fffdf8", "#fffdf8"), BORDER=("#d8cbb4", "#d8cbb4"),
                 TEXT=("#2a2118", "#2a2118"), MUTED=("#6b5d4a", "#6b5d4a"),
                 KEYCAP=("#e8dfcf", "#e8dfcf"), KEYCAP_HOVER=("#dccfba", "#dccfba"),
                 SWITCH_OFF=("#b9ab94", "#b9ab94")),
}
# theme name -> (CustomTkinter appearance mode, neutral palette)
THEME_LOOK = {"System": ("System", "default"), "Light": ("Light", "default"),
              "Dark": ("Dark", "default"), "Midnight": ("Dark", "midnight"),
              "Sand": ("Light", "sand")}
ACCENT_HEX = {"Blue": "#2f6bff", "Green": "#16a34a", "Purple": "#7c3aed",
              "Orange": "#ea580c", "Rose": "#e11d48", "Teal": "#0d9488"}


def _mix(a, b, t):
    """Blend colour a towards colour b by t (0..1); both are '#rrggbb'."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * (1 - t) + y * t) for x, y in zip(pa, pb))


def apply_palette(theme, accent):
    """Set the colour variables for a theme + accent. Returns the appearance mode to use."""
    mode, look = THEME_LOOK.get(theme, THEME_LOOK["System"])
    values = dict(_NEUTRAL[look])
    base = ACCENT_HEX.get(accent, ACCENT_HEX["Blue"])
    values.update(
        ACCENT=base,
        ACCENT_HOVER=_mix(base, "#000000", 0.18),
        ACCENT_TEXT=(_mix(base, "#000000", 0.25), _mix(base, "#ffffff", 0.35)),
        ACCENT_SOFT=(_mix(base, "#ffffff", 0.82), _mix(base, "#15171c", 0.78)),
    )
    globals().update(values)
    return mode


# ---------------------------------------------------------------------------
# Design tokens  (light, dark)
# ---------------------------------------------------------------------------
FONT = "Segoe UI"
BG = ("#e4e8ef", "#0f1115")
SIDEBAR = ("#ffffff", "#15171c")
CARD = ("#ffffff", "#1a1d23")
BORDER = ("#c3cbd8", "#2a2e36")
TEXT = ("#0b1220", "#f3f4f6")
MUTED = ("#4b5563", "#9ca3af")
ACCENT = "#2f6bff"
ACCENT_HOVER = "#1d55e0"
ACCENT_TEXT = ("#1d4ed8", "#6d9bff")
ACCENT_SOFT = ("#d3e0ff", "#1c2a4a")
KEYCAP = ("#d9dfea", "#2b303a")
KEYCAP_HOVER = ("#c7cfde", "#373d49")
SWITCH_OFF = ("#9aa4b5", "#3a3f4a")
DANGER = ("#c9252b", "#ff6b70")
DANGER_SOFT = ("#fbd5d7", "#3a1f22")
GREEN, AMBER = ("#15803d", "#22c55e"), ("#b45309", "#f59e0b")
BADGE = {"en": "#2f6bff", "ar": "#059669", "de": "#d97706", "fr": "#7c3aed", "es": "#dc2626",
         "ru": "#0891b2", "tr": "#be123c", "uk": "#ca8a04", "fa": "#15803d", "hi": "#c2410c",
         "ur": "#0f766e", "it": "#16a34a", "pt": "#9333ea", "el": "#0284c7"}

MODIFIER_KEYCODES = {16, 17, 18, 20, 91, 92, 93, 144, 145, 160, 161, 162, 163, 164, 165}
MOD_OF_KEYCODE = {16: "shift", 160: "shift", 161: "shift", 17: "ctrl", 162: "ctrl", 163: "ctrl",
                  18: "alt", 164: "alt", 165: "alt"}
HOTKEY_CANDIDATES = ["ctrl+alt+" + c for c in "LKJHGFDSAQWE"]


# ---------------------------------------------------------------------------
# Small widget helpers
# ---------------------------------------------------------------------------
def F(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def pretty_key(part):
    return part.upper() if len(part) == 1 else part.capitalize()


def keycaps(parent, hotkey):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    if not hotkey:
        ctk.CTkLabel(frame, text="—", text_color=MUTED, font=F(13)).pack()
        return frame
    for i, part in enumerate(hotkey.split("+")):
        text = pretty_key(part)
        ctk.CTkLabel(frame, text=text, font=F(12, "bold"), text_color=TEXT, fg_color=KEYCAP,
                     corner_radius=7, height=28, width=max(30, 14 + 8 * len(text))
                     ).pack(side="left", padx=(0 if i == 0 else 4, 0))
    return frame


def card(parent):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)


def button(parent, text, command, kind="ghost", width=None, height=34):
    styles = {
        "primary": dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white"),
        "ghost": dict(fg_color=KEYCAP, hover_color=KEYCAP_HOVER, text_color=TEXT),
        "danger": dict(fg_color="transparent", hover_color=DANGER_SOFT, text_color=DANGER),
        "nav": dict(fg_color="transparent", hover_color=ACCENT_SOFT, text_color=TEXT),
    }
    kw = styles[kind]
    if width:
        kw["width"] = width
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=10,
                         font=F(13, "bold"), **kw)


def dropdown(parent, values, command, width=120):
    return ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=36,
                             corner_radius=10, font=F(13, "bold"), dropdown_font=F(13),
                             fg_color=KEYCAP, button_color=KEYCAP, button_hover_color=KEYCAP_HOVER,
                             text_color=TEXT, dropdown_fg_color=CARD, dropdown_text_color=TEXT,
                             dropdown_hover_color=ACCENT_SOFT)


def switch(parent, variable, command):
    return ctk.CTkSwitch(parent, text="", width=44, variable=variable, command=command,
                         progress_color=ACCENT, button_color=("#334155", "#ffffff"),
                         button_hover_color=("#1e293b", "#f1f5f9"),
                         fg_color=SWITCH_OFF)


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------
def show_toast(root, text, ok=True):
    try:
        t = tk.Toplevel(root)
        t.withdraw()
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0.95)
        body = tk.Frame(t, bg="#111827")
        body.pack()
        tk.Frame(body, bg=ACCENT if ok else "#6b7280", width=5).pack(side="left", fill="y")
        tk.Label(body, text=text, bg="#111827", fg="white", padx=18, pady=11,
                 font=(FONT, 11)).pack(side="left")
        t.update_idletasks()
        winapi.set_no_activate(t)
        w, h = t.winfo_reqwidth(), t.winfo_reqheight()
        t.geometry("+%d+%d" % ((t.winfo_screenwidth() - w) // 2, t.winfo_screenheight() - h - 110))
        t.deiconify()
        t.after(1000, t.destroy)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shortcut recorder
# ---------------------------------------------------------------------------
class HotkeyDialog(ctk.CTkToplevel):
    def __init__(self, parent, taken, on_done):
        super().__init__(parent, fg_color=BG)
        self.taken, self.on_done, self._finished = taken, on_done, False
        self.title(tr("press_shortcut"))
        self.geometry("480x280")
        self.resizable(False, False)
        self.transient(parent)

        body = card(self)
        body.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(body, text=tr("press_shortcut"), font=F(17, "bold"), text_color=TEXT
                     ).pack(pady=(28, 16))
        self.preview = ctk.CTkFrame(body, fg_color="transparent", height=36)
        self.preview.pack()
        self.msg = tk.StringVar(self)
        ctk.CTkLabel(body, textvariable=self.msg, text_color=AMBER, font=F(12)).pack(pady=(12, 0))
        ctk.CTkLabel(body, text=tr("esc_cancel"), text_color=MUTED, font=F(12)
                     ).pack(side="bottom", pady=16)
        self._show([])
        self.bind("<KeyPress>", self._on_key)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))
        self.after(200, self._focus)

    def _focus(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def _show(self, parts):
        for w in self.preview.winfo_children():
            w.destroy()
        if parts:
            keycaps(self.preview, "+".join(parts)).pack()
        else:
            ctk.CTkLabel(self.preview, text="…", font=F(20, "bold"), text_color=MUTED).pack()

    @staticmethod
    def _mods(e):
        mods = []
        if e.state & 0x4 or MOD_OF_KEYCODE.get(e.keycode) == "ctrl":
            mods.append("ctrl")
        if e.state & 0x20000 or MOD_OF_KEYCODE.get(e.keycode) == "alt":
            mods.append("alt")
        if e.state & 0x1 or MOD_OF_KEYCODE.get(e.keycode) == "shift":
            mods.append("shift")
        return mods

    def _on_key(self, e):
        vk = e.keycode
        if vk == 27:
            return self._finish(None)
        mods = self._mods(e)
        if vk in MODIFIER_KEYCODES:
            self.msg.set("")
            return self._show(mods)
        name = vk_to_name(vk)
        if not name:
            return
        self._show(mods + [name])
        is_fkey = name[0] == "F" and name[1:].isdigit()
        if not mods and not is_fkey:
            self.msg.set(tr("need_modifier"))
            return
        hotkey = normalize_hotkey("+".join(mods + [name]))
        if not hotkey:
            return
        if hotkey in self.taken:
            self.msg.set(tr("hotkey_dup"))
            return
        self._finish(hotkey)

    def _finish(self, hotkey):
        if self._finished:
            return
        self._finished = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.on_done(hotkey)


def pretty_hotkey(hotkey):
    return " + ".join(pretty_key(p) for p in hotkey.split("+"))


apply_palette("System", "Blue")  # defaults, so the names above always exist


class ScrollFrame(ctk.CTkScrollableFrame):
    """Scroll area with eased, pixel-by-pixel mouse-wheel scrolling (instead of big jumps)."""

    NOTCH = 85    # pixels per wheel notch
    TICK = 14     # milliseconds between animation steps

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._goal, self._job = None, None
        try:
            self._parent_canvas.configure(yscrollincrement=1)
        except Exception:
            pass

    def _mouse_wheel_all(self, event):
        try:
            if not self._check_if_valid_scroll(event.widget) or getattr(self, "_shift_pressed", False):
                return
            canvas = self._parent_canvas
            if canvas.yview() == (0.0, 1.0):
                return
            num = getattr(event, "num", None)
            notches = (1 if num == 4 else -1) if num in (4, 5) else event.delta / 120.0
            box = canvas.bbox("all")
            limit = max(0, (box[3] if box else 0) - canvas.winfo_height())
            base = self._goal if self._goal is not None else canvas.canvasy(0)
            self._goal = min(limit, max(0, base - notches * self.NOTCH))
            if self._job is None:
                self._step()
        except Exception:
            self._goal, self._job = None, None

    def _step(self):
        self._job = None
        try:
            canvas = self._parent_canvas
            diff = self._goal - canvas.canvasy(0)
            if abs(diff) < 1:
                self._goal = None
                return
            move = diff * 0.3
            move = int(move) if abs(move) >= 1 else (1 if diff > 0 else -1)
            canvas.yview_scroll(move, "units")
            self._job = self.after(self.TICK, self._step)
        except Exception:
            self._goal, self._job = None, None

    def destroy(self):
        try:
            if self._job:
                self.after_cancel(self._job)
        except Exception:
            pass
        super().destroy()
