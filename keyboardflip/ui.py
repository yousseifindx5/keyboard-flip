"""Main window (CustomTkinter): sidebar navigation, card-based pages, popups glue."""
import itertools
import os
import queue
import threading
import time
import tkinter as tk
import traceback
import webbrowser

import customtkinter as ctk

from . import popups, updates, widgets as W, winapi
from .assets import ico_path, make_icon
from .config import (ACCENTS, APP_NAME, CONFIG_DIR, DOUBLE_TAP_KEYS, MAX_RULES, MAX_SNIPPETS,
                     RELEASES_URL, SNIPPET_TEXT_MAX, SNIPPET_TITLE_MAX, THEMES, VERSION, save_config)
from .i18n import UI_LANGUAGES, get_language, lang_name, set_language, tr
from .icons import nav_icon
from .layouts import LANGUAGES, LAYOUT_INFO, layout_available
from .log import log_error
from .winapi import normalize_hotkey

NAV = [("rules", "tab_rules"), ("keyboards", "tab_keyboards"), ("snippets", "tab_snippets"),
       ("history", "tab_history"), ("settings", "tab_settings"), ("about", "tab_about")]


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(ctk.CTk):
    def __init__(self, cfg, engine, events, tray_refresh, tray_stop, start_hidden=False):
        st = cfg["settings"]
        self._appearance = W.apply_palette(st["theme"], st["accent"])
        ctk.set_appearance_mode(self._appearance)
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=W.BG)
        if start_hidden:
            self.withdraw()
        self.cfg, self.engine, self.events = cfg, engine, events
        self.tray_refresh, self.tray_stop = tray_refresh, tray_stop
        self._keep, self._images, self._rule_vars = [], [], []
        self._warned_hide = False
        self.settings_scroll = None
        self._editing = None        # snippet being edited (its index), -1 = a new one, None = none
        self.update_info = None     # (version, url) once a newer release is known
        self.update_status = ""
        self.current_page = "rules"
        self.status_text = tk.StringVar(self)
        self.enabled_var = tk.BooleanVar(self, value=st["enabled"])

        self.geometry("1120x720")
        self.minsize(1040, 640)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._set_icon()
        self.build()
        self.after(40, self._poll)
        if not st["onboarded"] and not start_hidden:
            self.after(700, self.show_tour)
        self.after(3000, self.auto_check_updates)

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
                    self.iconbitmap(default=path)  # popups and re-created windows use it too
                    winapi.set_window_icon(self, path)  # exact sizes: sharp in the title bar and taskbar
                except Exception:
                    pass
            for ms in (250, 800, 2000):  # CustomTkinter resets the icon after theme changes; set it again
                self.after(ms, apply)
            self._apply_icon = apply
        except Exception:
            pass

    def _windows_set_titlebar_color(self, color_mode):
        """CustomTkinter refreshes the title bar on theme changes and that resets the icon to a feather."""
        super()._windows_set_titlebar_color(color_mode)
        apply = getattr(self, "_apply_icon", None)
        if apply:
            apply()
            for ms in (1, 30, 120, 400):
                self.after(ms, apply)

    def show_window(self):
        self.deiconify()
        self.after(100, getattr(self, '_apply_icon', lambda: None))
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide_window(self):
        self.withdraw()
        if not self._warned_hide:
            self._warned_hide = True
            W.show_toast(self, tr("still_running"), True)

    def quit_app(self):
        try:
            self.tray_stop()
        except Exception:
            pass
        self.engine.stop()
        self.destroy()

    def _poll(self):
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks % 100 == 0:
            try:
                self.engine.double_tap.ensure_alive()
            except Exception:
                pass
        try:
            while True:
                kind, *args = self.events.get_nowait()
                if kind == "quit":
                    return self.quit_app()
                try:
                    self._handle(kind, args)
                except Exception:
                    log_error()
        except queue.Empty:
            pass
        self.after(40, self._poll)

    def _handle(self, kind, args):
        if kind == "toast":
            if self.cfg["settings"]["notify"]:
                W.show_toast(self, *args)
        elif kind == "show":
            self.show_window()
        elif kind == "toggle":
            self.set_enabled(not self.cfg["settings"]["enabled"])
        elif kind == "history":
            if self.current_page == "history":
                self.refresh_history()
        elif kind == "preview":
            self._open_preview(*args)
        elif kind == "snippets":
            self._open_snippet_menu(*args)
        elif kind == "update":
            self._on_update(*args)

    def build(self, page=None):
        y = self._settings_y()
        for w in self.winfo_children():
            w.destroy()
        self._keep, self._images = [], []
        self.title(APP_NAME)
        rtl = W.rtl()
        side_col, main_col = (1, 0) if rtl else (0, 1)
        self.grid_columnconfigure(side_col, weight=0)
        self.grid_columnconfigure(main_col, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar(side_col)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=main_col, sticky="nsew")
        builders = {"rules": self._page_rules, "keyboards": self._page_keyboards,
                    "snippets": self._page_snippets, "history": self._page_history,
                    "settings": self._page_settings, "about": self._page_about}
        self.pages = {}
        for key, fn in builders.items():
            frame = ctk.CTkFrame(self.content, fg_color="transparent")
            fn(frame)
            self.pages[key] = frame
        self.show_page(page or self.current_page)
        self.refresh_status()
        if (page or self.current_page) == "settings":
            self._restore_y(y)
        self.after(50, getattr(self, "_apply_icon", lambda: None))

    def _settings_y(self):
        try:
            return self.settings_scroll._parent_canvas.yview()[0]
        except Exception:
            return 0.0

    def _restore_y(self, y):
        def go():
            try:
                self.settings_scroll._parent_canvas.yview_moveto(y)
            except Exception:
                pass
        self.after(30, go)
        self.after(120, go)

    def rebuild_settings(self):
        """Rebuild only the settings page and keep the scroll position (no jump to the top)."""
        y = self._settings_y()
        for w in self.pages["settings"].winfo_children():
            w.destroy()
        self._page_settings(self.pages["settings"])
        self._restore_y(y)

    def _build_sidebar(self, col=0):
        sb = ctk.CTkFrame(self, fg_color=W.SIDEBAR, corner_radius=0, width=236)
        sb.grid(row=0, column=col, sticky="nsew")
        sb.pack_propagate(False)
        ctk.CTkFrame(sb, width=1, fg_color=W.BORDER, corner_radius=0).pack(side=W.side("right"), fill="y")

        img = make_icon(96)
        logo = ctk.CTkImage(light_image=img, dark_image=img, size=(38, 38))
        self._images.append(logo)
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 22))
        ctk.CTkLabel(brand, image=logo, text="").pack(side=W.side("left"))
        ctk.CTkLabel(brand, text="Keyboard\nFlip", font=W.F(15, "bold"), text_color=W.TEXT,
                     justify=W.justify("left"), anchor=W.anchor("w")).pack(side=W.side("left"), padx=12)

        self.nav_buttons, self.nav_images = {}, {}
        for key, label in NAV:
            normal = ctk.CTkImage(light_image=nav_icon(key, (31, 41, 55, 255)),
                                  dark_image=nav_icon(key, (209, 213, 219, 255)), size=(20, 20))
            active = ctk.CTkImage(light_image=nav_icon(key, W.rgba(W.ACCENT_TEXT[0])),
                                  dark_image=nav_icon(key, W.rgba(W.ACCENT_TEXT[1])), size=(20, 20))
            self.nav_images[key] = (normal, active)
            b = W.button(sb, "  " + tr(label), lambda k=key: self.open_page(k), kind="nav", height=44)
            b.configure(anchor=W.anchor("w"), font=W.F(14, "bold"), image=normal, compound=W.side("left"))
            b.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[key] = b

        status = W.card(sb)
        status.pack(side="bottom", fill="x", padx=14, pady=18)
        top = ctk.CTkFrame(status, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))
        self.status_dot = ctk.CTkLabel(top, text="●", font=W.F(14), text_color=W.GREEN, width=16)
        self.status_dot.pack(side=W.side("left"))
        ctk.CTkLabel(top, text=tr("status_on"), font=W.F(13, "bold"), text_color=W.TEXT
                     ).pack(side=W.side("left"), padx=W.pad(4, 0))
        W.switch(top, self.enabled_var, lambda: self.set_enabled(self.enabled_var.get())
               ).pack(side=W.side("right"))
        ctk.CTkLabel(status, textvariable=self.status_text, font=W.F(12), text_color=W.MUTED,
                     wraplength=170, justify=W.justify("left"), anchor=W.anchor("w")
                     ).pack(fill="x", padx=16, pady=(0, 14))

    def show_page(self, key):
        self.current_page = key
        for k, frame in self.pages.items():
            frame.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=32, pady=(28, 18))
        for k, b in self.nav_buttons.items():
            active = k == key
            b.configure(fg_color=W.ACCENT_SOFT if active else "transparent",
                        text_color=W.ACCENT_TEXT if active else W.TEXT,
                        image=self.nav_images[k][1 if active else 0])

    def _header(self, page, title, subtitle, right=None):
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", pady=(0, 18))
        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side=W.side("left"), fill="x", expand=True)
        ctk.CTkLabel(texts, text=title, font=W.F(28, "bold"), text_color=W.TEXT, anchor=W.anchor("w")
                     ).pack(anchor=W.anchor("w"))
        ctk.CTkLabel(texts, text=subtitle, font=W.F(13), text_color=W.MUTED, anchor=W.anchor("w"),
                     justify=W.justify("left"), wraplength=560).pack(anchor=W.anchor("w"), pady=(4, 0))
        if right:
            right(row)

    # ----------------------------------------------------------------- status
    def refresh_status(self):
        st = self.cfg["settings"]
        if not st["enabled"]:
            text, color = tr("st_paused"), W.AMBER
        elif self.engine.failed:
            text = tr("st_failed").format(keys=", ".join(W.pretty_hotkey(k) for k in self.engine.failed))
            color = W.DANGER
        else:
            text, color = tr("st_active").format(n=self.engine.active), W.GREEN
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
            box.pack(side=W.side("right"))
            self.count_label = ctk.CTkLabel(box, text="", font=W.F(12), text_color=W.MUTED)
            self.count_label.pack(side=W.side("left"), padx=W.pad(0, 12))
            self.add_btn = W.button(box, tr("add_rule"), self.add_rule, "primary", width=170, height=38)
            self.add_btn.pack(side=W.side("left"))

        self._header(page, tr("tab_rules"), tr("sub_rules"), right)
        self.rules_frame = W.ScrollFrame(page, fg_color="transparent",
                                                  scrollbar_button_color=W.KEYCAP,
                                                  scrollbar_button_hover_color=W.KEYCAP_HOVER)
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
            empty = W.card(self.rules_frame)
            empty.pack(fill="x", pady=6)
            ctk.CTkLabel(empty, text="⇄", font=W.F(40), text_color=W.ACCENT_TEXT).pack(pady=(34, 4))
            ctk.CTkLabel(empty, text=tr("no_rules_title"), font=W.F(17, "bold"), text_color=W.TEXT).pack()
            ctk.CTkLabel(empty, text=tr("no_rules_desc"), font=W.F(13), text_color=W.MUTED
                         ).pack(pady=(4, 34))
            return

        code_of = {lang_name(c): c for c in LANGUAGES}
        names = [lang_name(c) for c in self.cfg["languages"]]
        for idx, rule in enumerate(rules):
            c = W.card(self.rules_frame)
            c.pack(fill="x", pady=5)
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=14)

            W.button(row, "✕", lambda i=idx: self.delete_rule(i), "danger", width=34).pack(side=W.side("right"))

            same = LANGUAGES[rule["src"]]["script"] == LANGUAGES[rule["dst"]]["script"]
            if same:
                ctk.CTkLabel(row, text=tr("same_alphabet"), font=W.F(12), text_color=W.MUTED
                             ).pack(side=W.side("right"), padx=14)
            else:
                both = tk.BooleanVar(self, value=rule["bidirectional"])
                self._rule_vars.append(both)
                ctk.CTkCheckBox(row, text=tr("both_ways"), variable=both, font=W.F(12), text_color=W.TEXT,
                                checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=2,
                                fg_color=W.ACCENT, hover_color=W.ACCENT_HOVER, border_color=W.MUTED,
                                command=lambda i=idx, v=both: self.set_rule(i, bidirectional=v.get())
                                ).pack(side=W.side("right"), padx=14)

            on = tk.BooleanVar(self, value=rule["enabled"])
            self._rule_vars.append(on)
            W.switch(row, on, lambda i=idx, v=on: self.set_rule(i, enabled=v.get())
                   ).pack(side=W.side("left"), padx=W.pad(0, 14))

            src = W.dropdown(row, names, lambda n, i=idx: self.set_rule(i, src=code_of[n]))
            src.set(lang_name(rule["src"]))
            src.pack(side=W.side("left"))
            W.button(row, "⇄", lambda i=idx: self.swap_rule(i), "ghost", width=34, height=36
                   ).pack(side=W.side("left"), padx=8)
            dst = W.dropdown(row, names, lambda n, i=idx: self.set_rule(i, dst=code_of[n]))
            dst.set(lang_name(rule["dst"]))
            dst.pack(side=W.side("left"))

            W.keycaps(row, rule["hotkey"]).pack(side=W.side("left"), padx=W.pad(22, 8))
            W.button(row, tr("change"), lambda i=idx: self.record_hotkey(i), "ghost", width=76
                   ).pack(side=W.side("left"))

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
        hotkey = next((normalize_hotkey(h) for h in W.HOTKEY_CANDIDATES
                       if normalize_hotkey(h) not in used), "ctrl+alt+L")
        rules.append({"src": src, "dst": dst, "hotkey": hotkey, "enabled": True, "bidirectional": False})
        self.apply()
        self.refresh_rules()

    def _used_hotkeys(self, skip_rule=None, skip_key=None):
        """Shortcuts already taken by a conversion or by the undo / case / snippets keys."""
        used = {normalize_hotkey(r["hotkey"]) for i, r in enumerate(self.cfg["rules"]) if i != skip_rule}
        for name in ("undo_hotkey", "case_hotkey", "snippets_hotkey"):
            value = self.cfg["settings"].get(name, "")
            if value and name != skip_key:
                used.add(normalize_hotkey(value))
        return used

    def record_hotkey(self, idx):
        self.engine.suspend()  # otherwise Windows swallows the keys we want to record

        def done(hotkey):
            if hotkey:
                self.cfg["rules"][idx]["hotkey"] = hotkey
            self.apply()
            self.refresh_rules()

        W.HotkeyDialog(self, self._used_hotkeys(skip_rule=idx), done)

    # -------------------------------------------------------- page: keyboards
    def _page_keyboards(self, page):
        self._header(page, tr("tab_keyboards"), tr("sub_keyboards"))
        grid = W.ScrollFrame(page, fg_color="transparent",
                                      scrollbar_button_color=W.KEYCAP,
                                      scrollbar_button_hover_color=W.KEYCAP_HOVER)
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="cols")
        for i, code in enumerate(LANGUAGES):
            c = W.card(grid)
            c.grid(row=i // 2, column=(1 - i % 2) if W.rtl() else i % 2, sticky="nsew", padx=6, pady=6)
            top = ctk.CTkFrame(c, fg_color="transparent")
            top.pack(fill="x", padx=18, pady=(18, 10))
            ctk.CTkLabel(top, text=code.upper(), font=W.F(14, "bold"), text_color="white",
                         fg_color=W.BADGE[code], corner_radius=12, width=46, height=46).pack(side=W.side("left"))
            ctk.CTkLabel(top, text=lang_name(code), font=W.F(16, "bold"), text_color=W.TEXT
                         ).pack(side=W.side("left"), padx=14)
            var = tk.BooleanVar(self, value=code in self.cfg["languages"])
            self._keep.append(var)
            W.switch(top, var, lambda c=code, v=var: self.toggle_language(c, v)).pack(side=W.side("right"))

            bottom = ctk.CTkFrame(c, fg_color="transparent")
            bottom.pack(fill="x", padx=18, pady=(0, 18))
            ctk.CTkLabel(bottom, text=tr("layout"), font=W.F(12), text_color=W.MUTED, width=56, anchor=W.anchor("w")
                         ).pack(side=W.side("left"))
            ids = LANGUAGES[code]["layouts"]
            menu = W.dropdown(bottom, [LAYOUT_INFO[i][0] for i in ids], None, width=250)
            menu.configure(command=lambda n, c=code, m=menu: self.set_layout(c, n, m))
            menu.set(LAYOUT_INFO[self.cfg["layouts"][code]][0])
            if len(ids) == 1:
                menu.configure(state="disabled")
            menu.pack(side=W.side("left"), fill="x", expand=True)

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
                     font=W.F(11, "bold"), text_color=W.MUTED, anchor=W.anchor("w")
                     ).pack(fill="x", padx=4, pady=(16, 6))
        c = W.card(parent)
        c.pack(fill="x")
        return c

    def _setting_row(self, parent, title, desc, build_right, last=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side=W.side("right"))
        build_right(right)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side=W.side("left"), fill="x", expand=True)
        ctk.CTkLabel(left, text=title, font=W.F(14, "bold"), text_color=W.TEXT, anchor=W.anchor("w")).pack(anchor=W.anchor("w"))
        if desc:
            ctk.CTkLabel(left, text=desc, font=W.F(12), text_color=W.MUTED, anchor=W.anchor("w"), justify=W.justify("left"),
                         wraplength=520).pack(anchor=W.anchor("w"), pady=(2, 0))
        if not last:
            ctk.CTkFrame(parent, height=1, fg_color=W.BORDER).pack(fill="x", padx=20)

    def _page_settings(self, page):
        self._header(page, tr("tab_settings"), tr("sub_settings"))
        scroll = W.ScrollFrame(page, fg_color="transparent",
                                        scrollbar_button_color=W.KEYCAP,
                                        scrollbar_button_hover_color=W.KEYCAP_HOVER)
        scroll.pack(fill="both", expand=True)
        self.settings_scroll = scroll
        st = self.cfg["settings"]

        def toggle_row(parent, title, desc, var, command, last=False):
            self._setting_row(parent, title, desc, lambda r: W.switch(r, var, command).pack(), last)

        def saver(key, var, after=None):
            def cb():
                st[key] = var.get()
                save_config(self.cfg)
                if after:
                    after()
            return cb

        def flag(key):
            var = tk.BooleanVar(self, value=st[key])
            self._keep.append(var)
            return var

        # General
        g = self._section(scroll, tr("sec_general"))
        auto_var = tk.BooleanVar(self, value=winapi.is_autostart())
        self._keep.append(auto_var)

        def on_auto():
            try:
                winapi.set_autostart(auto_var.get())
            except Exception:
                auto_var.set(not auto_var.get())
            st["autostart"] = auto_var.get()
            save_config(self.cfg)

        notify_v, last_v, prev_v, hist_v = flag("notify"), flag("convert_last_word"), flag("preview"), flag("history")
        toggle_row(g, tr("settings_enabled"), tr("settings_enabled_d"), self.enabled_var,
                   lambda: self.set_enabled(self.enabled_var.get()))
        toggle_row(g, tr("settings_autostart"), tr("settings_autostart_d"), auto_var, on_auto)
        toggle_row(g, tr("settings_notify"), tr("settings_notify_d"), notify_v, saver("notify", notify_v))
        toggle_row(g, tr("settings_lastword"), tr("settings_lastword_d"), last_v,
                   saver("convert_last_word", last_v))
        toggle_row(g, tr("settings_preview"), tr("settings_preview_d"), prev_v, saver("preview", prev_v))
        toggle_row(g, tr("settings_history"), tr("settings_history_d"), hist_v,
                   saver("history", hist_v, after=lambda: self.engine.history.clear() if not st["history"] else None),
                   last=True)

        # Shortcuts
        s = self._section(scroll, tr("sec_shortcuts"))

        def hotkey_row(title, desc, name, last=False, clearable=True, unique=True):
            def right(r):
                W.keycaps(r, st.get(name, "")).pack(side=W.side("left"), padx=W.pad(0, 10))
                W.button(r, tr("change"), lambda: self.record_setting_hotkey(name, unique), "ghost",
                         width=76).pack(side=W.side("left"))
                if clearable and st.get(name):
                    W.button(r, "✕", lambda: self.clear_setting_hotkey(name), "danger",
                             width=34).pack(side=W.side("left"), padx=W.pad(6, 0))
            self._setting_row(s, title, desc, right, last)

        hotkey_row(tr("undo_title"), tr("undo_desc"), "undo_hotkey")
        hotkey_row(tr("case_title"), tr("case_desc"), "case_hotkey")
        reselect_v = flag("case_reselect")
        toggle_row(s, tr("settings_reselect"), tr("settings_reselect_d"), reselect_v,
                   saver("case_reselect", reselect_v))
        hotkey_row(tr("snippets_title"), tr("snippets_desc"), "snippets_hotkey")

        # double-tap: which key, and which conversion it runs
        keys = list(DOUBLE_TAP_KEYS)
        key_names = {"off": tr("dtap_off"), "shift": tr("dtap_key_shift"), "ctrl": tr("dtap_key_ctrl")}
        rule_labels = ["%d.  %s → %s" % (i + 1, lang_name(r["src"]), lang_name(r["dst"]))
                       for i, r in enumerate(self.cfg["rules"])]

        def dtap_key(display):
            st["double_tap_key"] = next(k for k in keys if key_names[k] == display)
            self.apply()

        def dtap_rule(display):
            if display in rule_labels:
                st["double_tap_rule"] = rule_labels.index(display)
                self.apply()

        def dtap_right(r):
            m1 = W.dropdown(r, [key_names[k] for k in keys], dtap_key, width=150)
            m1.set(key_names[st["double_tap_key"]])
            m1.pack(side=W.side("left"))
            m2 = W.dropdown(r, rule_labels or ["—"], dtap_rule, width=190)
            index = st["double_tap_rule"]
            m2.set(rule_labels[index] if 0 <= index < len(rule_labels) else (rule_labels or ["—"])[0])
            m2.pack(side=W.side("left"), padx=W.pad(8, 0))

        self._setting_row(s, tr("dtap_title"), tr("dtap_desc"), dtap_right)

        # Excluded programs
        x = self._section(scroll, tr("sec_excluded"))
        box = ctk.CTkFrame(x, fg_color="transparent")
        box.pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(box, text=tr("excluded_title"), font=W.F(14, "bold"), text_color=W.TEXT, anchor=W.anchor("w")
                     ).pack(anchor=W.anchor("w"))
        ctk.CTkLabel(box, text=tr("excluded_hint"), font=W.F(12), text_color=W.MUTED, anchor=W.anchor("w"),
                     justify=W.justify("left"), wraplength=640).pack(anchor=W.anchor("w"), pady=(3, 12))
        self.chips = ctk.CTkFrame(box, fg_color="transparent")
        self.chips.pack(fill="x")
        self.render_excluded()
        entry_row = ctk.CTkFrame(box, fg_color="transparent")
        entry_row.pack(fill="x", pady=(12, 0))
        self.ex_entry = ctk.CTkEntry(entry_row, placeholder_text=tr("excluded_ph"), height=36,
                                     corner_radius=10, border_width=0, fg_color=W.KEYCAP,
                                     text_color=W.TEXT, font=W.F(13))
        self.ex_entry.pack(side=W.side("left"), fill="x", expand=True)
        self.ex_entry.bind("<Return>", lambda e: self.add_excluded_from_entry())
        W.button(entry_row, tr("add"), self.add_excluded_from_entry, "primary", width=80
                 ).pack(side=W.side("left"), padx=8)
        W.button(entry_row, tr("browse"), self.browse_app, "ghost", width=120).pack(side=W.side("left"))

        # Appearance
        a = self._section(scroll, tr("sec_appearance"))
        theme_names = {t: tr("theme_" + t) for t in THEMES}
        accent_names = {c: tr("accent_" + c) for c in ACCENTS}

        def lang_right(r):
            m = W.dropdown(r, list(UI_LANGUAGES.values()), self.change_ui_language, width=150)
            m.set(UI_LANGUAGES[get_language()])
            m.pack()

        def theme_right(r):
            m = W.dropdown(r, list(theme_names.values()), self.change_theme, width=150)
            m.set(theme_names[st["theme"]])
            m.pack()

        def accent_right(r):
            m = W.dropdown(r, list(accent_names.values()), self.change_accent, width=150)
            m.set(accent_names[st["accent"]])
            m.pack()

        self._setting_row(a, tr("settings_ui_lang"), None, lang_right)
        self._setting_row(a, tr("settings_theme"), None, theme_right)
        self._setting_row(a, tr("settings_accent"), None, accent_right, last=True)

        # Updates
        u = self._section(scroll, tr("sec_updates"))
        upd_v = flag("check_updates")

        def on_upd():
            st["check_updates"] = upd_v.get()
            save_config(self.cfg)
            if upd_v.get():
                self.check_updates()

        toggle_row(u, tr("settings_updates"), tr("settings_updates_d"), upd_v, on_upd, last=True)

    def render_excluded(self):
        for w in self.chips.winfo_children():
            w.destroy()
        apps = self.cfg["settings"]["excluded_apps"]
        if not apps:
            ctk.CTkLabel(self.chips, text=tr("no_excluded"), font=W.F(12), text_color=W.MUTED).pack(anchor=W.anchor("w"))
            return
        self.chips.grid_columnconfigure((0, 1, 2), weight=1, uniform="chips")
        for i, name in enumerate(apps):
            chip = ctk.CTkFrame(self.chips, fg_color=W.KEYCAP, corner_radius=9)
            chip.grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(chip, text=name, font=W.F(12, "bold"), text_color=W.TEXT, anchor=W.anchor("w")
                         ).pack(side=W.side("left"), padx=W.pad(12, 2), pady=5, fill="x", expand=True)
            ctk.CTkButton(chip, text="✕", width=24, height=24, corner_radius=8, fg_color="transparent",
                          hover_color=W.DANGER_SOFT, text_color=W.DANGER, font=W.F(12, "bold"),
                          command=lambda n=name: self.remove_excluded(n)).pack(side=W.side("left"), padx=W.pad(0, 4))

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

    def browse_app(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self, title=tr("browse_title"),
                                          filetypes=[("Programs", "*.exe"), ("*", "*.*")])
        if path:
            self.add_excluded(os.path.basename(path))

    # undo shortcut -----------------------------------------------------------
    def record_setting_hotkey(self, name, unique=True):
        self.engine.suspend()

        def done(hotkey):
            if hotkey:
                self.cfg["settings"][name] = hotkey
            self.apply()
            self.after(1, self.rebuild_settings)

        W.HotkeyDialog(self, self._used_hotkeys(skip_key=name) if unique else set(), done)

    def clear_setting_hotkey(self, name):
        self.cfg["settings"][name] = ""
        self.apply()
        self.after(1, self.rebuild_settings)

    def change_ui_language(self, display):
        code = next(c for c, n in UI_LANGUAGES.items() if n == display)
        self.cfg["settings"]["ui_language"] = code
        set_language(code)
        save_config(self.cfg)
        self.tray_refresh()
        self.after(1, lambda: self.build("settings"))

    def change_theme(self, display):
        names = {tr("theme_" + t): t for t in THEMES}
        self.cfg["settings"]["theme"] = names.get(display, "System")
        save_config(self.cfg)
        self.restyle("settings")

    def change_accent(self, display):
        names = {tr("accent_" + c): c for c in ACCENTS}
        self.cfg["settings"]["accent"] = names.get(display, "Blue")
        save_config(self.cfg)
        self.restyle("settings")

    def restyle(self, page):
        """Apply the chosen theme / accent colour: new palette, then rebuild every page."""
        st = self.cfg["settings"]
        mode = W.apply_palette(st["theme"], st["accent"])
        if mode != getattr(self, "_mode", None):  # only a light/dark switch touches the title bar (and the icon)
            self._appearance = mode
            ctk.set_appearance_mode(mode)
        self.configure(fg_color=W.BG)
        self.after(1, lambda: self.build(page))

    def _page_about(self, page):
        self._header(page, tr("tab_about"), "")
        c = W.card(page)
        c.pack(fill="x")
        img = make_icon(192)
        big = ctk.CTkImage(light_image=img, dark_image=img, size=(96, 96))
        self._images.append(big)
        ctk.CTkLabel(c, image=big, text="").pack(pady=(34, 10))
        ctk.CTkLabel(c, text=APP_NAME, font=W.F(26, "bold"), text_color=W.TEXT).pack()
        ctk.CTkLabel(c, text="v" + VERSION, font=W.F(13), text_color=W.MUTED).pack(pady=(2, 14))
        ctk.CTkLabel(c, text=tr("about_text"), font=W.F(14), text_color=W.TEXT, justify="center").pack()
        self.update_label = ctk.CTkLabel(c, text=self.update_status, font=W.F(13, "bold"),
                                         text_color=W.ACCENT_TEXT, wraplength=520)
        self.update_label.pack(pady=(16, 0))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(pady=(14, 34))
        if self.update_info:
            W.button(row, tr("download"), lambda: webbrowser.open(self.update_info[1] or RELEASES_URL),
                     "primary", width=130, height=38).pack(side=W.side("left"), padx=4)
        W.button(row, tr("check_now"), lambda: self.check_updates(manual=True), "ghost", width=130,
                 height=38).pack(side=W.side("left"), padx=4)
        W.button(row, tr("tour_again"), self.show_tour, "ghost", width=190, height=38
                 ).pack(side=W.side("left"), padx=4)
        W.button(row, tr("open_folder"), self.open_folder, "ghost", width=190, height=38
                 ).pack(side=W.side("left"), padx=4)

    def open_folder(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.startfile(CONFIG_DIR)
        except Exception:
            pass

    # ------------------------------------------------------------ navigation
    def open_page(self, key):
        """Show a page, rebuilding the ones whose content depends on other pages."""
        if key == "settings":
            for w in self.pages["settings"].winfo_children():
                w.destroy()
            self._page_settings(self.pages["settings"])
        elif key == "history":
            self.refresh_history()
        self.show_page(key)

    # ---------------------------------------------------------- page: snippets
    def _page_snippets(self, page):
        def right(row):
            box = ctk.CTkFrame(row, fg_color="transparent")
            box.pack(side=W.side("right"))
            self.snip_count = ctk.CTkLabel(box, text="", font=W.F(12), text_color=W.MUTED)
            self.snip_count.pack(side=W.side("left"), padx=W.pad(0, 12))
            self.snip_add = W.button(box, tr("add_snippet"), lambda: self.edit_snippet(-1), "primary",
                                     width=170, height=38)
            self.snip_add.pack(side=W.side("left"))

        self._header(page, tr("tab_snippets"), tr("sub_snippets"), right)
        key = W.pretty_hotkey(self.cfg["settings"].get("snippets_hotkey", ""))
        if key:
            ctk.CTkLabel(page, text=tr("snippets_hint").format(key=key), font=W.F(12), text_color=W.MUTED,
                         anchor=W.anchor("w")).pack(fill="x", pady=(0, 10))
        self.snip_frame = W.ScrollFrame(page, fg_color="transparent",
                                                 scrollbar_button_color=W.KEYCAP,
                                                 scrollbar_button_hover_color=W.KEYCAP_HOVER)
        self.snip_frame.pack(fill="both", expand=True)
        self.refresh_snippets()

    def refresh_snippets(self):
        for w in self.snip_frame.winfo_children():
            w.destroy()
        items = self.cfg["snippets"]
        self.snip_count.configure(text=tr("snippets_count").format(n=len(items), m=MAX_SNIPPETS))
        self.snip_add.configure(state="normal" if len(items) < MAX_SNIPPETS and self._editing is None
                                else "disabled")
        if self._editing is not None:
            self._snippet_form(self._editing)
        if not items and self._editing is None:
            empty = W.card(self.snip_frame)
            empty.pack(fill="x", pady=6)
            ctk.CTkLabel(empty, text="✎", font=W.F(40), text_color=W.ACCENT_TEXT).pack(pady=(34, 4))
            ctk.CTkLabel(empty, text=tr("no_snippets_title"), font=W.F(17, "bold"), text_color=W.TEXT).pack()
            ctk.CTkLabel(empty, text=tr("no_snippets_desc"), font=W.F(13), text_color=W.MUTED,
                         wraplength=520).pack(pady=(4, 34))
            return
        for i, item in enumerate(items):
            if i == self._editing:
                continue
            c = W.card(self.snip_frame)
            c.pack(fill="x", pady=5)
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=12)
            W.button(row, "✕", lambda n=i: self.delete_snippet(n), "danger", width=34).pack(side=W.side("right"))
            W.button(row, tr("snippet_edit"), lambda n=i: self.edit_snippet(n), "ghost", width=76
                     ).pack(side=W.side("right"), padx=8)
            texts = ctk.CTkFrame(row, fg_color="transparent")
            texts.pack(side=W.side("left"), fill="x", expand=True)
            ctk.CTkLabel(texts, text="%d   %s" % (i + 1, item["title"]) if i < 9 else item["title"],
                         font=W.F(14, "bold"), text_color=W.TEXT, anchor=W.anchor("w")).pack(anchor=W.anchor("w"))
            preview = item["text"].replace("\r", " ").replace("\n", " ")
            ctk.CTkLabel(texts, text=preview if len(preview) <= 90 else preview[:90] + "…",
                         font=W.F(12), text_color=W.MUTED, anchor=W.anchor("w"), justify=W.justify("left"),
                         wraplength=560).pack(anchor=W.anchor("w"))

    def _snippet_form(self, index):
        item = self.cfg["snippets"][index] if 0 <= index < len(self.cfg["snippets"]) else {"title": "", "text": ""}
        c = W.card(self.snip_frame)
        c.pack(fill="x", pady=5)
        box = ctk.CTkFrame(c, fg_color="transparent")
        box.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(box, text=tr("snippet_title"), font=W.F(12, "bold"), text_color=W.MUTED, anchor=W.anchor("w")
                     ).pack(anchor=W.anchor("w"))
        title = ctk.CTkEntry(box, placeholder_text=tr("snippet_ph_title"), height=36, corner_radius=10,
                             border_width=0, fg_color=W.KEYCAP, text_color=W.TEXT, font=W.F(13))
        title.pack(fill="x", pady=(4, 12))
        if item["title"]:
            title.insert(0, item["title"])
        ctk.CTkLabel(box, text=tr("snippet_text"), font=W.F(12, "bold"), text_color=W.MUTED, anchor=W.anchor("w")
                     ).pack(anchor=W.anchor("w"))
        text = ctk.CTkTextbox(box, height=96, corner_radius=10, border_width=0, fg_color=W.KEYCAP,
                              text_color=W.TEXT, font=W.F(13))
        text.pack(fill="x", pady=(4, 6))
        text.insert("1.0", item["text"])
        msg = tk.StringVar(self)
        self._keep.append(msg)
        ctk.CTkLabel(box, textvariable=msg, font=W.F(12), text_color=W.AMBER, anchor=W.anchor("w")).pack(anchor=W.anchor("w"))
        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))

        def save():
            t, body = title.get().strip(), text.get("1.0", "end-1c")
            if not t or not body.strip():
                return msg.set(tr("snippet_need"))
            entry = {"title": t[:SNIPPET_TITLE_MAX], "text": body[:SNIPPET_TEXT_MAX]}
            if 0 <= index < len(self.cfg["snippets"]):
                self.cfg["snippets"][index] = entry
            elif len(self.cfg["snippets"]) < MAX_SNIPPETS:
                self.cfg["snippets"].append(entry)
            else:
                return msg.set(tr("snippet_max").format(n=MAX_SNIPPETS))
            save_config(self.cfg)
            self._editing = None
            self.after(1, self.refresh_snippets)

        def cancel():
            self._editing = None
            self.after(1, self.refresh_snippets)

        W.button(buttons, tr("snippet_save"), save, "primary", width=100, height=36).pack(side=W.side("left"))
        W.button(buttons, tr("snippet_cancel"), cancel, "ghost", width=100, height=36
                 ).pack(side=W.side("left"), padx=8)
        title.focus_set()

    def edit_snippet(self, index):
        self._editing = index
        self.refresh_snippets()

    def delete_snippet(self, index):
        if 0 <= index < len(self.cfg["snippets"]):
            del self.cfg["snippets"][index]
            save_config(self.cfg)
        self._editing = None
        self.after(1, self.refresh_snippets)

    def _open_snippet_menu(self, hwnd):
        popups.SnippetMenu(self, self.cfg["snippets"],
                           lambda text: self.engine.paste_snippet(hwnd, text))

    def _open_preview(self, message, result, decide):
        try:
            popups.PreviewPopup(self, message, result, decide)
        except Exception:
            log_error()
            decide(True)  # never block a conversion because the box failed

    # ----------------------------------------------------------- page: history
    def _page_history(self, page):
        def right(row):
            W.button(row, tr("history_clear"), self.clear_history, "ghost", width=90, height=38
                     ).pack(side=W.side("right"))

        self._header(page, tr("tab_history"), tr("sub_history"), right)
        ctk.CTkLabel(page, text="🔒  " + tr("history_note"), font=W.F(12), text_color=W.MUTED,
                     anchor=W.anchor("w")).pack(fill="x", pady=(0, 10))
        self.hist_frame = W.ScrollFrame(page, fg_color="transparent",
                                                 scrollbar_button_color=W.KEYCAP,
                                                 scrollbar_button_hover_color=W.KEYCAP_HOVER)
        self.hist_frame.pack(fill="both", expand=True)
        self.refresh_history()

    @staticmethod
    def _short(text, n=140):
        text = text.replace("\r", " ").replace("\n", " ")
        return text if len(text) <= n else text[:n] + "…"

    def refresh_history(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()
        if not self.cfg["settings"]["history"]:
            ctk.CTkLabel(self.hist_frame, text=tr("history_off"), font=W.F(13), text_color=W.MUTED
                         ).pack(pady=40)
            return
        items = list(self.engine.history)
        if not items:
            empty = W.card(self.hist_frame)
            empty.pack(fill="x", pady=6)
            ctk.CTkLabel(empty, text="🕘", font=W.F(40), text_color=W.ACCENT_TEXT).pack(pady=(34, 4))
            ctk.CTkLabel(empty, text=tr("history_empty"), font=W.F(17, "bold"), text_color=W.TEXT).pack()
            ctk.CTkLabel(empty, text=tr("history_empty_d"), font=W.F(13), text_color=W.MUTED
                         ).pack(pady=(4, 34))
            return
        for item in items:
            c = W.card(self.hist_frame)
            c.pack(fill="x", pady=5)
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=12)
            buttons = ctk.CTkFrame(row, fg_color="transparent")
            buttons.pack(side=W.side("right"))
            W.button(buttons, tr("history_copy"), lambda t=item["after"]: self.copy_text(t), "ghost",
                     width=120, height=30).pack(side=W.side("left"))
            W.button(buttons, tr("history_copy_before"), lambda t=item["before"]: self.copy_text(t), "ghost",
                     width=120, height=30).pack(side=W.side("left"), padx=W.pad(6, 0))
            texts = ctk.CTkFrame(row, fg_color="transparent")
            texts.pack(side=W.side("left"), fill="x", expand=True)
            stamp = time.strftime("%d/%m/%Y  %I:%M:%S %p", time.localtime(item["time"]))  # 05/11/2026  12:02:11 AM
            ctk.CTkLabel(texts, text="%s   ·   %s" % (stamp, item["message"]), font=W.F(12, "bold"),
                         text_color=W.ACCENT_TEXT, anchor=W.anchor("w")).pack(anchor=W.anchor("w"))
            ctk.CTkLabel(texts, text=self._short(item["before"]), font=W.F(13), text_color=W.MUTED,
                         anchor=W.anchor("w"), justify=W.justify("left"), wraplength=480).pack(anchor=W.anchor("w"))
            ctk.CTkLabel(texts, text="→  " + self._short(item["after"]), font=W.F(14), text_color=W.TEXT,
                         anchor=W.anchor("w"), justify=W.justify("left"), wraplength=480).pack(anchor=W.anchor("w"))

    def clear_history(self):
        self.engine.clear_history()
        self.refresh_history()

    def copy_text(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except tk.TclError:
            return
        self.flash(tr("history_copied"))

    # ------------------------------------------------------------ welcome tour
    def show_tour(self):
        rules = [r for r in self.cfg["rules"] if r.get("enabled", True)]
        key = rules[0]["hotkey"] if rules else "ctrl+alt+L"
        undo = self.cfg["settings"].get("undo_hotkey") or "ctrl+alt+Z"
        self.show_window()
        self.engine.practice = True
        popups.Tour(self, key, undo, self._tour_done)

    def _tour_done(self):
        self.engine.practice = False
        self.cfg["settings"]["onboarded"] = True
        save_config(self.cfg)

    # ----------------------------------------------------------------- updates
    def auto_check_updates(self):
        st = self.cfg["settings"]
        if st["check_updates"] and time.time() - st["last_update_check"] > 86400:
            self.check_updates()

    def check_updates(self, manual=False):
        self.update_status = tr("update_checking")
        self._show_update_status()
        threading.Thread(target=lambda: self.events.put(("update", updates.check_latest(), manual)),
                         daemon=True).start()

    def _show_update_status(self):
        try:
            self.update_label.configure(text=self.update_status)
        except Exception:
            pass

    def _on_update(self, info, manual):
        self.cfg["settings"]["last_update_check"] = time.time()
        save_config(self.cfg)
        if info is None:
            self.update_status = tr("update_failed") if manual else ""
        elif updates.is_newer(info[0]):
            self.update_info = info
            self.update_status = tr("update_available").format(v=info[0])
            W.show_toast(self, self.update_status, True)
            self.after(1, lambda: self.build(self.current_page))
        else:
            ahead = updates.is_newer(VERSION, info[0])
            self.update_status = (tr("update_ahead") if ahead else tr("update_latest")) if manual else ""
        self._show_update_status()
