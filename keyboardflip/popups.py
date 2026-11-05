"""Small extra windows: the preview box, the snippets menu and the welcome tour."""
import tkinter as tk

import customtkinter as ctk

from . import widgets as W
from .assets import make_icon
from .config import APP_NAME
from .i18n import tr

PREVIEW_TIMEOUT = 12  # seconds; then the preview cancels itself


def _place_near_pointer(win):
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = min(max(win.winfo_pointerx() - 20, 0), max(win.winfo_screenwidth() - w - 10, 0))
    y = min(max(win.winfo_pointery() + 16, 0), max(win.winfo_screenheight() - h - 50, 0))
    win.geometry("+%d+%d" % (x, y))


def _take_focus(win):
    try:
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass


class PreviewPopup(ctk.CTkToplevel):
    """Shows what the text would become. Enter applies it, Esc cancels."""

    def __init__(self, parent, message, result, decide):
        super().__init__(parent, fg_color=W.BORDER)
        self.decide, self._done = decide, False
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        body = W.card(self)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(body, text="%s  ·  %s" % (tr("preview_title"), message), font=W.F(12, "bold"),
                     text_color=W.MUTED, anchor=W.anchor("w")).pack(fill="x", padx=16, pady=(12, 4))
        shown = result if len(result) <= 400 else result[:400] + "…"
        ctk.CTkLabel(body, text=shown, font=W.F(15), text_color=W.TEXT, justify=W.justify("left"), anchor=W.anchor("w"),
                     wraplength=420).pack(fill="x", padx=16, pady=(0, 8))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row, text=tr("preview_hint"), font=W.F(11), text_color=W.MUTED).pack(side=W.side("left"))
        W.button(row, tr("preview_cancel"), lambda: self.finish(False), "ghost", width=84,
                 height=30).pack(side=W.side("right"))
        W.button(row, tr("preview_apply"), lambda: self.finish(True), "primary", width=84,
                 height=30).pack(side=W.side("right"), padx=W.pad(0, 6))
        self.bind("<Return>", lambda e: self.finish(True))
        self.bind("<Escape>", lambda e: self.finish(False))
        _place_near_pointer(self)
        self.after(60, lambda: _take_focus(self))
        self.after(PREVIEW_TIMEOUT * 1000, lambda: self.finish(False))

    def finish(self, ok):
        if self._done:
            return
        self._done = True
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.decide(ok)


class SnippetMenu(ctk.CTkToplevel):
    """A small list of snippets. Up/Down + Enter, a number key, or a click picks one."""

    def __init__(self, parent, snippets, on_pick):
        super().__init__(parent, fg_color=W.BORDER)
        self.snippets, self.on_pick, self._done, self.index = snippets, on_pick, False, 0
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        body = W.card(self)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(body, text=tr("menu_title"), font=W.F(13, "bold"), text_color=W.TEXT,
                     anchor=W.anchor("w")).pack(fill="x", padx=14, pady=(12, 6))
        self.rows = []
        if not snippets:
            ctk.CTkLabel(body, text=tr("menu_empty"), font=W.F(12), text_color=W.MUTED,
                         wraplength=300, justify=W.justify("left")).pack(padx=14, pady=(2, 10))
        for i, item in enumerate(snippets[:9]):
            preview = item["text"].replace("\r", " ").replace("\n", " ")
            if len(preview) > 34:
                preview = preview[:34] + "…"
            row = ctk.CTkButton(body, text="%d   %s    %s" % (i + 1, item["title"], preview),
                                anchor=W.anchor("w"), height=34, width=360, corner_radius=8, font=W.F(13),
                                fg_color="transparent", hover_color=W.ACCENT_SOFT, text_color=W.TEXT,
                                command=lambda n=i: self.pick(n))
            row.pack(fill="x", padx=8, pady=1)
            self.rows.append(row)
        ctk.CTkLabel(body, text=tr("menu_hint"), font=W.F(11), text_color=W.MUTED, anchor=W.anchor("w")
                     ).pack(fill="x", padx=14, pady=(8, 10))
        self._highlight()
        self.bind("<Up>", lambda e: self._move(-1))
        self.bind("<Down>", lambda e: self._move(1))
        self.bind("<Return>", lambda e: self.pick(self.index))
        self.bind("<Escape>", lambda e: self.close())
        for n in range(1, 10):
            self.bind(str(n), lambda e, k=n - 1: self.pick(k))
        _place_near_pointer(self)
        self.after(60, lambda: _take_focus(self))
        self.after(400, lambda: self.bind("<FocusOut>", self._lost_focus))

    def _lost_focus(self, _event):
        self.after(150, lambda: self.close() if not self._done and self.focus_displayof() is None
                   else None)

    def _highlight(self):
        for i, row in enumerate(self.rows):
            row.configure(fg_color=W.ACCENT_SOFT if i == self.index else "transparent")

    def _move(self, step):
        if self.rows:
            self.index = (self.index + step) % len(self.rows)
            self._highlight()

    def close(self):
        if not self._done:
            self._done = True
            try:
                self.destroy()
            except tk.TclError:
                pass

    def pick(self, n):
        if self._done or not 0 <= n < len(self.rows):
            return
        text = self.snippets[n]["text"]
        self.close()
        self.on_pick(text)


class Tour(ctk.CTkToplevel):
    """First-run welcome tour: what it does, how to use it, and a box to try it in."""
    STEPS = 4

    def __init__(self, parent, rule_hotkey, undo_hotkey, on_close):
        super().__init__(parent, fg_color=W.BG)
        self.rule_hotkey, self.undo_hotkey, self.on_close = rule_hotkey, undo_hotkey, on_close
        self.step, self._closed = 0, False
        self.title(APP_NAME)
        self.geometry("580x470")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.body = W.card(self)
        self.body.pack(fill="both", expand=True, padx=18, pady=(18, 8))
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 16))
        self.skip_btn = W.button(footer, tr("ob_skip"), self.close, "nav", width=90)
        self.skip_btn.pack(side=W.side("left"))
        self.next_btn = W.button(footer, "", self.next, "primary", width=110, height=38)
        self.next_btn.pack(side=W.side("right"))
        self.back_btn = W.button(footer, tr("ob_back"), self.back, "ghost", width=90, height=38)
        self.back_btn.pack(side=W.side("right"), padx=8)
        self.dots = ctk.CTkLabel(footer, text="", font=W.F(14), text_color=W.MUTED)
        self.dots.pack(side=W.side("left"), expand=True)
        self.after(150, self._focus)
        self.show()

    def _focus(self):
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def next(self):
        if self.step >= self.STEPS - 1:
            return self.close()
        self.step += 1
        self.show()

    def back(self):
        if self.step > 0:
            self.step -= 1
            self.show()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.on_close()

    def _title(self, title, subtitle=""):
        ctk.CTkLabel(self.body, text=title, font=W.F(24, "bold"), text_color=W.TEXT,
                     wraplength=480).pack(pady=(34, 6))
        if subtitle:
            ctk.CTkLabel(self.body, text=subtitle, font=W.F(14), text_color=W.MUTED,
                         wraplength=460, justify="center").pack(pady=(0, 10))

    def show(self):
        for w in self.body.winfo_children():
            w.destroy()
        key = W.pretty_hotkey(self.rule_hotkey)
        if self.step == 0:
            img = ctk.CTkImage(light_image=make_icon(160), dark_image=make_icon(160), size=(84, 84))
            self._image = img
            ctk.CTkLabel(self.body, image=img, text="").pack(pady=(40, 0))
            self._title(tr("ob_welcome"), tr("ob_welcome_d"))
        elif self.step == 1:
            self._title(tr("ob_how"))
            steps = [tr("ob_step1"), tr("ob_step2").format(key=key),
                     tr("ob_step3").format(undo=W.pretty_hotkey(self.undo_hotkey) or "Ctrl + Alt + Z")]
            for n, text in enumerate(steps, start=1):
                row = ctk.CTkFrame(self.body, fg_color="transparent")
                row.pack(fill="x", padx=40, pady=8)
                ctk.CTkLabel(row, text=str(n), width=34, height=34, corner_radius=10, font=W.F(14, "bold"),
                             text_color="white", fg_color=W.ACCENT).pack(side=W.side("left"))
                ctk.CTkLabel(row, text=text, font=W.F(14), text_color=W.TEXT, wraplength=400,
                             justify=W.justify("left"), anchor=W.anchor("w")).pack(side=W.side("left"), padx=14)
            W.keycaps(self.body, self.rule_hotkey).pack(pady=(14, 0))
        elif self.step == 2:
            self._title(tr("ob_try"), tr("ob_try_d").format(key=key))
            box = ctk.CTkTextbox(self.body, height=110, width=440, corner_radius=12, font=W.F(20),
                                 fg_color=W.KEYCAP, text_color=W.TEXT, border_width=0)
            box.pack(pady=(4, 10))
            box.insert("1.0", tr("ob_sample"))
            box.focus_set()
            box.tag_add("sel", "1.0", "end-1c")
            W.keycaps(self.body, self.rule_hotkey).pack()
        else:
            self._title(tr("ob_done"), tr("ob_done_d"))
        last = self.step == self.STEPS - 1
        self.next_btn.configure(text=tr("ob_start") if last else tr("ob_next"))
        self.skip_btn.configure(text="" if last else tr("ob_skip"), state="disabled" if last else "normal")
        if self.step == 0:
            self.back_btn.pack_forget()
        else:
            self.back_btn.pack(side=W.side("right"), padx=8)
        self.dots.configure(text="●  " * self.step + "◉  " + "○  " * (self.STEPS - self.step - 1))
