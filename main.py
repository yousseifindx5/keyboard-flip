"""Keyboard Flip - entry point."""
import queue
import sys
import threading


def main():
    if sys.platform != "win32":
        print("Keyboard Flip runs on Windows only.")
        return

    import ctypes
    try:  # own identity, so the taskbar shows our logo and not python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KeyboardFlip.App")
    except Exception:
        pass

    from keyboardflip import winapi
    mutex, already_running = winapi.acquire_single_instance()
    if already_running:
        winapi.signal_existing()  # ask the running copy to show its window
        return
    show_event = winapi.create_show_event()

    import pystray
    from keyboardflip.assets import tray_icon_image
    from keyboardflip.config import APP_NAME, load_config
    from keyboardflip.engine import Engine
    from keyboardflip.i18n import set_language, tr
    from keyboardflip.ui import MainWindow

    cfg = load_config()
    set_language(cfg["settings"]["ui_language"])
    events = queue.Queue()
    engine = Engine(cfg, lambda text, ok=True: events.put(("toast", text, ok)))

    def build_menu():
        return pystray.Menu(
            pystray.MenuItem(tr("tray_open"), lambda icon, item: events.put(("show",)), default=True),
            pystray.MenuItem(tr("tray_enabled"), lambda icon, item: events.put(("toggle",)),
                             checked=lambda item: cfg["settings"]["enabled"]),
            pystray.MenuItem(tr("tray_quit"), lambda icon, item: events.put(("quit",))),
        )

    icon = pystray.Icon("KeyboardFlip", tray_icon_image(), APP_NAME, build_menu())

    def refresh_tray():
        icon.menu = build_menu()
        try:
            icon.update_menu()
        except Exception:
            pass

    window = MainWindow(cfg, engine, events, refresh_tray, icon.stop)
    icon.run_detached()

    stop = threading.Event()

    def watch_show_event():
        while not stop.is_set():
            if winapi.wait_event(show_event, 400):
                events.put(("show",))

    threading.Thread(target=watch_show_event, daemon=True).start()

    engine.reload()
    window.refresh_status()
    if "--minimized" in sys.argv:
        window.withdraw()
    window.mainloop()
    stop.set()
    engine.stop()


if __name__ == "__main__":
    main()
