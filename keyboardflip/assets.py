"""App icon / logo files live in the assets folder (icon.png + icon.ico)."""
import os
import sys


def resource_path(relative):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


def _draw_fallback(size):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=60, fill=(80, 100, 240, 255))
    return img.resize((size, size), Image.LANCZOS)


def make_icon(size=256):
    """The logo as a PIL image of the given size."""
    from PIL import Image
    path = resource_path(os.path.join("assets", "icon.png"))
    try:
        return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return _draw_fallback(size)


def ico_path():
    """Path of the multi-size .ico used for the window / taskbar icon (None if missing)."""
    path = resource_path(os.path.join("assets", "icon.ico"))
    return path if os.path.exists(path) else None


def tray_icon_image():
    """Pixel-exact logo for the system tray (16/20/24/32 px depending on DPI)."""
    from PIL import Image
    want = 16
    try:
        import ctypes
        want = ctypes.windll.user32.GetSystemMetrics(49) or 16  # SM_CXSMICON
    except Exception:
        pass
    path = ico_path()
    if path:
        try:
            ico = Image.open(path)
            sizes = sorted(ico.ico.sizes())
            best = next((s for s in sizes if s[0] >= want), sizes[-1])
            return ico.ico.getimage(best).convert("RGBA")
        except Exception:
            pass
    return make_icon(max(want, 32))
