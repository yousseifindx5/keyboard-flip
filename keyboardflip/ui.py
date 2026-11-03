"""Main window (CustomTkinter): sidebar navigation, card-based pages, shortcut recorder, toast."""
import itertools
import os
import queue
import sys
import tkinter as tk
import traceback

import customtkinter as ctk

from . import winapi
from .assets import ico_path, make_icon
from .icons import nav_icon
from .config import APP_NAME, CONFIG_DIR, MAX_RULES, VERSION, save_config
from .i18n import UI_LANGUAGES, get_language, lang_name, set_language, tr
from .layouts import LANGUAGES, LAYOUT_INFO, layout_available
from .log import log_error
from .winapi import normalize_hotkey, vk_to_name

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
BADGE = {"en": "#2f6bff", "ar": "#059669", "de": "#d97706",
         "fr": "#7c3aed", "es": "#dc2626", "ru": "#0891b2"}

MODIFIER_KEYCODES = {16, 17, 18, 20, 91, 92, 93, 144, 145, 160, 161, 162, 163, 164, 165}
MOD_OF_KEYCODE = {16: "shift", 160: "shift", 161: "shift", 17: "ctrl", 162: "ctrl", 163: "ctrl",
                  18: "alt", 164: "alt", 165: "alt"}
HOTKEY_CANDIDATES = ["ctrl+alt+" + c for c in "LKJHGFDSAQWE"]
NAV = [("rules", "tab_rules"), ("keyboards", "tab_keyboards"),
       ("settings", "tab_settings"), ("about", "tab_about")]


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
        tk.Frame(body, bg="#2f6bff" if ok else "#6b7280", width=5).pack(side="left", fill="y")
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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(ctk.CTk):
    def __init__(self, cfg, engine, events, tray_refresh, tray_stop, start_hidden=False):
        super().__init__(fg_color=BG)
        if start_hidden:
            self.withdraw()
        self.cfg, self.engine, self.events = cfg, engine, events
        self.tray_refresh, self.tray_stop = tray_refresh, tray_stop
        self._keep, self._images, self._rule_vars = [], [], []
        self._warned_hide = False
        self._picking = False
        self.current_page = "rules"
        self.status_text = tk.StringVar(self)
        self.enabled_var = tk.BooleanVar(self, value=cfg["settings"]["enabled"])

        ctk.set_appearance_mode(cfg["settings"]["theme"])
        ctk.set_default_color_theme("blue")
        self.geometry("1120x720")
        self.minsize(1040, 640)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._set_icon()
        self.build()
        self.after(40, self._poll)

    def report_callback_exception(self, exc, val, tb):
        log_error("".join(traceback.format_exception(exc, val, tb)))  # Tk callbacks must never crash the app

    # ------------------------------------------------------------- window ops
    def _set_icon(self):
        try:
            path = ico_path()
            if not path:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                path = os.path.join(CONFIG_DIR, "icon.ico")
                make_icon(256).save(path, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

            def apply():
                try:
                    self.iconbitmap(path)
                except Exception:
                    pass
            self.after(250, apply)  # CustomTkinter sets its own icon at ~200 ms
        except Exception:
            pass

    def show_window(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide_window(self):
        self.withdraw()
        if not self._warned_hide:
            self._warned_hide = True
            show_toast(self, tr("still_running"), True)

    def quit_app(self):
        try:
            self.tray_stop()
        except Exception:
            pass
        self.engine.stop()
        self.destroy()

    def _poll(self):
        try:
            while True:
                kind, *args = self.events.get_nowait()
                if kind == "toast":
                    if self.cfg["settings"]["notify"]:
                        show_toast(self, *args)
                elif kind == "show":
                    self.show_window()
                elif kind == "quit":
                    return self.quit_app()
                elif kind == "toggle":
                    self.set_enabled(not self.cfg["settings"]["enabled"])
        except queue.Empty:
            pass
        self.after(40, self._poll)

    # ------------------------------------------------------------------ shell
    def build(self, page=None):
        for w in self.winfo_children():
            w.destroy()
        self._keep, self._images = [], []
        self.title(APP_NAME)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        builders = {"rules": self._page_rules, "keyboards": self._page_keyboards,
                    "settings": self._page_settings, "about": self._page_about}
        self.pages = {}
        for key, fn in builders.items():
            frame = ctk.CTkFrame(self.content, fg_color="transparent")
            fn(frame)
            self.pages[key] = frame
        self.show_page(page or self.current_page)
        self.refresh_status()

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=236)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.pack_propagate(False)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER, corner_radius=0).pack(side="right", fill="y")

        img = make_icon(96)
        logo = ctk.CTkImage(light_image=img, dark_image=img, size=(38, 38))
        self._images.append(logo)
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 22))
        ctk.CTkLabel(brand, image=logo, text="").pack(side="left")
        ctk.CTkLabel(brand, text="Keyboard\nFlip", font=F(15, "bold"), text_color=TEXT,
                     justify="left", anchor="w").pack(side="left", padx=12)

        self.nav_buttons, self.nav_images = {}, {}
        for key, label in NAV:
            normal = ctk.CTkImage(light_image=nav_icon(key, (31, 41, 55, 255)),
                                  dark_image=nav_icon(key, (209, 213, 219, 255)), size=(20, 20))
            active = ctk.CTkImage(light_image=nav_icon(key, (29, 78, 216, 255)),
                                  dark_image=nav_icon(key, (109, 155, 255, 255)), size=(20, 20))
            self.nav_images[key] = (normal, active)
            b = button(sb, "  " + tr(label), lambda k=key: self.show_page(k), kind="nav", height=44)
            b.configure(anchor="w", font=F(14, "bold"), image=normal, compound="left")
            b.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[key] = b

        status = card(sb)
        status.pack(side="bottom", fill="x", padx=14, pady=18)
        top = ctk.CTkFrame(status, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))
        self.status_dot = ctk.CTkLabel(top, text="●", font=F(14), text_color=GREEN, width=16)
        self.status_dot.pack(side="left")
        ctk.CTkLabel(top, text=tr("status_on"), font=F(13, "bold"), text_color=TEXT
                     ).pack(side="left", padx=(4, 0))
        switch(top, self.enabled_var, lambda: self.set_enabled(self.enabled_var.get())
               ).pack(side="right")
        ctk.CTkLabel(status, textvariable=self.status_text, font=F(12), text_color=MUTED,
                     wraplength=170, justify="left", anchor="w"
                     ).pack(fill="x", padx=16, pady=(0, 14))

    def show_page(self, key):
        self.current_page = key
        for k, frame in self.pages.items():
            frame.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=32, pady=(28, 18))
        for k, b in self.nav_buttons.items():
            active = k == key
            b.configure(fg_color=ACCENT_SOFT if active else "transparent",
                        text_color=ACCENT_TEXT if active else TEXT,
                        image=self.nav_images[k][1 if active else 0])

    def _header(self, page, title, subtitle, right=None):
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", pady=(0, 18))
        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(texts, text=title, font=F(28, "bold"), text_color=TEXT, anchor="w"
                     ).pack(anchor="w")
        ctk.CTkLabel(texts, text=subtitle, font=F(13), text_color=MUTED, anchor="w",
                     justify="left", wraplength=560).pack(anchor="w", pady=(4, 0))
        if right:
            right(row)

    # ----------------------------------------------------------------- status
    def refresh_status(self):
        st = self.cfg["settings"]
        if not st["enabled"]:
            text, color = tr("st_paused"), AMBER
        elif self.engine.failed:
            text = tr("st_failed").format(keys=", ".join(pretty_hotkey(k) for k in self.engine.failed))
            color = DANGER
        else:
            text, color = tr("st_active").format(n=self.engine.active), GREEN
        self.status_text.set(text)
        try:
            self.status_dot.configure(text_color=color)
        except Exception:
            pass

    def flash(self, text):
        self.status_text.set(text)
        self.after(3000, self.refresh_status)

    def apply(self):
        save_config(self.cfg)
        self.engine.reload()
        self.refresh_status()
        self.tray_refresh()

    def set_enabled(self, value):
        self.cfg["settings"]["enabled"] = value
        self.enabled_var.set(value)
        self.apply()

    # ------------------------------------------------------------ page: rules
    def _page_rules(self, page):
        def right(row):
            box = ctk.CTkFrame(row, fg_color="transparent")
            box.pack(side="right")
            self.count_label = ctk.CTkLabel(box, text="", font=F(12), text_color=MUTED)
            self.count_label.pack(side="left", padx=(0, 12))
            self.add_btn = button(box, tr("add_rule"), self.add_rule, "primary", width=170, height=38)
            self.add_btn.pack(side="left")

        self._header(page, tr("tab_rules"), tr("sub_rules"), right)
        self.rules_frame = ctk.CTkScrollableFrame(page, fg_color="transparent",
                                                  scrollbar_button_color=KEYCAP,
                                                  scrollbar_button_hover_color=KEYCAP_HOVER)
        self.rules_frame.pack(fill="both", expand=True)
        self.refresh_rules()

    def refresh_rules(self):
        for w in self.rules_frame.winfo_children():
            w.destroy()
        self._rule_vars = []
        rules = self.cfg["rules"]
        self.count_label.configure(text=tr("rules_count").format(n=len(rules), m=MAX_RULES))
        self.add_btn.configure(state="normal" if len(rules) < MAX_RULES else "disabled")

        if not rules:
            empty = card(self.rules_frame)
            empty.pack(fill="x", pady=6)
            ctk.CTkLabel(empty, text="⇄", font=F(40), text_color=ACCENT_TEXT).pack(pady=(34, 4))
            ctk.CTkLabel(empty, text=tr("no_rules_title"), font=F(17, "bold"), text_color=TEXT).pack()
            ctk.CTkLabel(empty, text=tr("no_rules_desc"), font=F(13), text_color=MUTED
                         ).pack(pady=(4, 34))
            return

        code_of = {lang_name(c): c for c in LANGUAGES}
        names = [lang_name(c) for c in self.cfg["languages"]]
        for idx, rule in enumerate(rules):
            c = card(self.rules_frame)
            c.pack(fill="x", pady=5)
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=14)

            button(row, "✕", lambda i=idx: self.delete_rule(i), "danger", width=34).pack(side="right")

            same = LANGUAGES[rule["src"]]["script"] == LANGUAGES[rule["dst"]]["script"]
            if same:
                ctk.CTkLabel(row, text=tr("same_alphabet"), font=F(12), text_color=MUTED
                             ).pack(side="right", padx=14)
            else:
                both = tk.BooleanVar(self, value=rule["bidirectional"])
                self._rule_vars.append(both)
                ctk.CTkCheckBox(row, text=tr("both_ways"), variable=both, font=F(12), text_color=TEXT,
                                checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=2,
                                fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=MUTED,
                                command=lambda i=idx, v=both: self.set_rule(i, bidirectional=v.get())
                                ).pack(side="right", padx=14)

            on = tk.BooleanVar(self, value=rule["enabled"])
            self._rule_vars.append(on)
            switch(row, on, lambda i=idx, v=on: self.set_rule(i, enabled=v.get())
                   ).pack(side="left", padx=(0, 14))

            src = dropdown(row, names, lambda n, i=idx: self.set_rule(i, src=code_of[n]))
            src.set(lang_name(rule["src"]))
            src.pack(side="left")
            button(row, "⇄", lambda i=idx: self.swap_rule(i), "ghost", width=34, height=36
                   ).pack(side="left", padx=8)
            dst = dropdown(row, names, lambda n, i=idx: self.set_rule(i, dst=code_of[n]))
            dst.set(lang_name(rule["dst"]))
            dst.pack(side="left")

            keycaps(row, rule["hotkey"]).pack(side="left", padx=(22, 8))
            button(row, tr("change"), lambda i=idx: self.record_hotkey(i), "ghost", width=76
                   ).pack(side="left")

    def set_rule(self, idx, **changes):
        rule = self.cfg["rules"][idx]
        rule.update(changes)
        langs = self.cfg["languages"]
        if rule["src"] == rule["dst"]:
            if "src" in changes:
                rule["dst"] = next(c for c in langs if c != rule["src"])
            else:
                rule["src"] = next(c for c in langs if c != rule["dst"])
        self.apply()
        if "src" in changes or "dst" in changes:
            self.after(1, self.refresh_rules)

    def swap_rule(self, idx):
        rule = self.cfg["rules"][idx]
        rule["src"], rule["dst"] = rule["dst"], rule["src"]
        self.apply()
        self.after(1, self.refresh_rules)

    def delete_rule(self, idx):
        del self.cfg["rules"][idx]
        self.apply()
        self.after(1, self.refresh_rules)

    def add_rule(self):
        rules = self.cfg["rules"]
        if len(rules) >= MAX_RULES:
            return self.flash(tr("max_rules").format(n=MAX_RULES))
        pairs = list(itertools.permutations(self.cfg["languages"], 2))
        used_pairs = {(r["src"], r["dst"]) for r in rules}
        src, dst = next((p for p in pairs if p not in used_pairs), pairs[0])
        used = self._used_hotkeys()
        hotkey = next((normalize_hotkey(h) for h in HOTKEY_CANDIDATES
                       if normalize_hotkey(h) not in used), "ctrl+alt+L")
        rules.append({"src": src, "dst": dst, "hotkey": hotkey, "enabled": True, "bidirectional": False})
        self.apply()
        self.refresh_rules()

    def _used_hotkeys(self, skip_rule=None, skip_undo=False):
        used = {normalize_hotkey(r["hotkey"]) for i, r in enumerate(self.cfg["rules"]) if i != skip_rule}
        undo = self.cfg["settings"].get("undo_hotkey", "")
        if undo and not skip_undo:
            used.add(normalize_hotkey(undo))
        return used

    def record_hotkey(self, idx):
        self.engine.suspend()  # otherwise Windows swallows the keys we want to record

        def done(hotkey):
            if hotkey:
                self.cfg["rules"][idx]["hotkey"] = hotkey
            self.apply()
            self.refresh_rules()

        HotkeyDialog(self, self._used_hotkeys(skip_rule=idx), done)

    # -------------------------------------------------------- page: keyboards
    def _page_keyboards(self, page):
        self._header(page, tr("tab_keyboards"), tr("sub_keyboards"))
        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        for i, code in enumerate(LANGUAGES):
            c = card(grid)
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            top = ctk.CTkFrame(c, fg_color="transparent")
            top.pack(fill="x", padx=18, pady=(18, 10))
            ctk.CTkLabel(top, text=code.upper(), font=F(14, "bold"), text_color="white",
                         fg_color=BADGE[code], corner_radius=12, width=46, height=46).pack(side="left")
            ctk.CTkLabel(top, text=lang_name(code), font=F(16, "bold"), text_color=TEXT
                         ).pack(side="left", padx=14)
            var = tk.BooleanVar(self, value=code in self.cfg["languages"])
            self._keep.append(var)
            switch(top, var, lambda c=code, v=var: self.toggle_language(c, v)).pack(side="right")

            bottom = ctk.CTkFrame(c, fg_color="transparent")
            bottom.pack(fill="x", padx=18, pady=(0, 18))
            ctk.CTkLabel(bottom, text=tr("layout"), font=F(12), text_color=MUTED, width=56, anchor="w"
                         ).pack(side="left")
            ids = LANGUAGES[code]["layouts"]
            menu = dropdown(bottom, [LAYOUT_INFO[i][0] for i in ids], None, width=250)
            menu.configure(command=lambda n, c=code, m=menu: self.set_layout(c, n, m))
            menu.set(LAYOUT_INFO[self.cfg["layouts"][code]][0])
            if len(ids) == 1:
                menu.configure(state="disabled")
            menu.pack(side="left", fill="x", expand=True)

    def toggle_language(self, code, var):
        chosen = {c for c in LANGUAGES if c in self.cfg["languages"]}
        if var.get():
            chosen.add(code)
        else:
            chosen.discard(code)
        if len(chosen) < 2:
            var.set(True)
            return self.flash(tr("need_two_langs"))
        self.cfg["languages"] = [c for c in LANGUAGES if c in chosen]
        for rule in self.cfg["rules"]:
            if code not in self.cfg["languages"] and code in (rule["src"], rule["dst"]):
                rule["enabled"] = False
        self.apply()
        self.refresh_rules()

    def set_layout(self, code, display_name, menu):
        layout_id = next(i for i in LANGUAGES[code]["layouts"] if LAYOUT_INFO[i][0] == display_name)
        if not layout_available(layout_id):
            menu.set(LAYOUT_INFO[self.cfg["layouts"][code]][0])
            return self.flash(tr("layout_unavailable"))
        self.cfg["layouts"][code] = layout_id
        self.apply()

    # --------------------------------------------------------- page: settings
    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title.upper() if get_language() == "en" else title,
                     font=F(11, "bold"), text_color=MUTED, anchor="w"
                     ).pack(fill="x", padx=4, pady=(16, 6))
        c = card(parent)
        c.pack(fill="x")
        return c

    def _setting_row(self, parent, title, desc, build_right, last=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right")
        build_right(right)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text=title, font=F(14, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        if desc:
            ctk.CTkLabel(left, text=desc, font=F(12), text_color=MUTED, anchor="w", justify="left",
                         wraplength=520).pack(anchor="w", pady=(2, 0))
        if not last:
            ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", padx=20)

    def _page_settings(self, page):
        self._header(page, tr("tab_settings"), tr("sub_settings"))
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent",
                                        scrollbar_button_color=KEYCAP,
                                        scrollbar_button_hover_color=KEYCAP_HOVER)
        scroll.pack(fill="both", expand=True)
        st = self.cfg["settings"]

        def toggle_row(parent, title, desc, var, command, last=False):
            self._setting_row(parent, title, desc, lambda r: switch(r, var, command).pack(), last)

        def saver(key, var):
            def cb():
                st[key] = var.get()
                save_config(self.cfg)
            return cb

        # General
        g = self._section(scroll, tr("sec_general"))
        auto_var = tk.BooleanVar(self, value=winapi.is_autostart())
        notify_var = tk.BooleanVar(self, value=st["notify"])
        last_var = tk.BooleanVar(self, value=st["convert_last_word"])
        self._keep += [auto_var, notify_var, last_var]

        def on_auto():
            try:
                winapi.set_autostart(auto_var.get())
            except Exception:
                auto_var.set(not auto_var.get())
            st["autostart"] = auto_var.get()
            save_config(self.cfg)

        toggle_row(g, tr("settings_enabled"), tr("settings_enabled_d"), self.enabled_var,
                   lambda: self.set_enabled(self.enabled_var.get()))
        toggle_row(g, tr("settings_autostart"), tr("settings_autostart_d"), auto_var, on_auto)
        toggle_row(g, tr("settings_notify"), tr("settings_notify_d"), notify_var, saver("notify", notify_var))
        toggle_row(g, tr("settings_lastword"), tr("settings_lastword_d"), last_var,
                   saver("convert_last_word", last_var), last=True)

        # Shortcuts
        s = self._section(scroll, tr("sec_shortcuts"))

        def undo_right(r):
            keycaps(r, st.get("undo_hotkey", "")).pack(side="left", padx=(0, 10))
            button(r, tr("change"), self.record_undo, "ghost", width=76).pack(side="left")
            if st.get("undo_hotkey"):
                button(r, "✕", self.clear_undo, "danger", width=34).pack(side="left", padx=(6, 0))

        self._setting_row(s, tr("undo_title"), tr("undo_desc"), undo_right, last=True)

        # Excluded programs
        x = self._section(scroll, tr("sec_excluded"))
        box = ctk.CTkFrame(x, fg_color="transparent")
        box.pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(box, text=tr("excluded_title"), font=F(14, "bold"), text_color=TEXT, anchor="w"
                     ).pack(anchor="w")
        ctk.CTkLabel(box, text=tr("excluded_hint"), font=F(12), text_color=MUTED, anchor="w",
                     justify="left", wraplength=640).pack(anchor="w", pady=(3, 12))
        self.chips = ctk.CTkFrame(box, fg_color="transparent")
        self.chips.pack(fill="x")
        self.render_excluded()
        entry_row = ctk.CTkFrame(box, fg_color="transparent")
        entry_row.pack(fill="x", pady=(12, 0))
        self.ex_entry = ctk.CTkEntry(entry_row, placeholder_text=tr("excluded_ph"), height=36,
                                     corner_radius=10, border_width=0, fg_color=KEYCAP, text_color=TEXT,
                                     font=F(13))
        self.ex_entry.pack(side="left", fill="x", expand=True)
        self.ex_entry.bind("<Return>", lambda e: self.add_excluded_from_entry())
        button(entry_row, tr("add"), self.add_excluded_from_entry, "primary", width=80
               ).pack(side="left", padx=8)
        self.pick_btn = button(entry_row, tr("pick_app"), self.pick_app, "ghost", width=130)
        self.pick_btn.pack(side="left")

        # Appearance
        a = self._section(scroll, tr("sec_appearance"))
        def lang_right(r):
            m = dropdown(r, list(UI_LANGUAGES.values()), self.change_ui_language, width=150)
            m.set(UI_LANGUAGES[get_language()])
            m.pack()

        def theme_right(r):
            m = dropdown(r, ["System", "Light", "Dark"], self.change_theme, width=150)
            m.set(st["theme"])
            m.pack()

        self._setting_row(a, tr("settings_ui_lang"), None, lang_right)
        self._setting_row(a, tr("settings_theme"), None, theme_right, last=True)

    # excluded programs -------------------------------------------------------
    def render_excluded(self):
        for w in self.chips.winfo_children():
            w.destroy()
        apps = self.cfg["settings"]["excluded_apps"]
        if not apps:
            ctk.CTkLabel(self.chips, text=tr("no_excluded"), font=F(12), text_color=MUTED).pack(anchor="w")
            return
        for i, name in enumerate(apps):
            chip = ctk.CTkFrame(self.chips, fg_color=KEYCAP, corner_radius=9)
            chip.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 8), pady=4)
            ctk.CTkLabel(chip, text=name, font=F(12, "bold"), text_color=TEXT
                         ).pack(side="left", padx=(12, 2), pady=5)
            ctk.CTkButton(chip, text="✕", width=24, height=24, corner_radius=8, fg_color="transparent",
                          hover_color=DANGER_SOFT, text_color=DANGER, font=F(12, "bold"),
                          command=lambda n=name: self.remove_excluded(n)).pack(side="left", padx=(0, 4))

    def add_excluded(self, name):
        name = name.strip().lower()
        if not name:
            return
        if not name.endswith(".exe"):
            name += ".exe"
        apps = self.cfg["settings"]["excluded_apps"]
        if name not in apps:
            apps.append(name)
            save_config(self.cfg)
        self.render_excluded()

    def add_excluded_from_entry(self):
        self.add_excluded(self.ex_entry.get())
        self.ex_entry.delete(0, "end")

    def remove_excluded(self, name):
        apps = self.cfg["settings"]["excluded_apps"]
        if name in apps:
            apps.remove(name)
            save_config(self.cfg)
        self.after(1, self.render_excluded)

    def pick_app(self):
        if not self._picking:
            self._picking = True
            self._pick_tick(3)

    def _pick_tick(self, n):
        try:
            if n > 0:
                self.pick_btn.configure(text=tr("pick_wait").format(n=n))
                return self.after(1000, lambda: self._pick_tick(n - 1))
            self.pick_btn.configure(text=tr("pick_app"))
        except Exception:
            pass
        self._picking = False
        name = winapi.foreground_process_name()
        own = {os.path.basename(sys.executable).lower(), "python.exe", "pythonw.exe", "keyboardflip.exe"}
        if not name or name in own:
            return self.flash(tr("pick_self"))
        self.add_excluded(name)

    # undo shortcut -----------------------------------------------------------
    def record_undo(self):
        self.engine.suspend()

        def done(hotkey):
            if hotkey:
                self.cfg["settings"]["undo_hotkey"] = hotkey
            self.apply()
            self.build("settings")

        HotkeyDialog(self, self._used_hotkeys(skip_undo=True), done)

    def clear_undo(self):
        self.cfg["settings"]["undo_hotkey"] = ""
        self.apply()
        self.after(1, lambda: self.build("settings"))

    def change_ui_language(self, display):
        code = next(c for c, n in UI_LANGUAGES.items() if n == display)
        self.cfg["settings"]["ui_language"] = code
        set_language(code)
        save_config(self.cfg)
        self.tray_refresh()
        self.after(1, lambda: self.build("settings"))

    def change_theme(self, value):
        self.cfg["settings"]["theme"] = value
        ctk.set_appearance_mode(value)
        save_config(self.cfg)

    # ------------------------------------------------------------- page: about
    def _page_about(self, page):
        self._header(page, tr("tab_about"), "")
        c = card(page)
        c.pack(fill="x")
        img = make_icon(192)
        big = ctk.CTkImage(light_image=img, dark_image=img, size=(96, 96))
        self._images.append(big)
        ctk.CTkLabel(c, image=big, text="").pack(pady=(34, 10))
        ctk.CTkLabel(c, text=APP_NAME, font=F(26, "bold"), text_color=TEXT).pack()
        ctk.CTkLabel(c, text="v" + VERSION, font=F(13), text_color=MUTED).pack(pady=(2, 14))
        ctk.CTkLabel(c, text=tr("about_text"), font=F(14), text_color=TEXT, justify="center").pack()
        button(c, tr("open_folder"), self.open_folder, "ghost", width=200, height=38).pack(pady=(22, 34))

    def open_folder(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.startfile(CONFIG_DIR)
        except Exception:
            pass


def pretty_hotkey(hotkey):
    return " + ".join(pretty_key(p) for p in hotkey.split("+"))
