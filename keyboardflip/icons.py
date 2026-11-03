"""Crisp line icons for the sidebar, drawn with Pillow (no image files needed)."""
import math

from PIL import Image, ImageDraw

_S = 320  # drawing canvas; downsampled for smooth edges


def _finish(img):
    return img.resize((80, 80), Image.LANCZOS)


def _swap(c):
    img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(50, 105), (215, 105)], fill=c, width=24)
    d.polygon([(205, 55), (275, 105), (205, 155)], fill=c)
    d.line([(105, 215), (270, 215)], fill=c, width=24)
    d.polygon([(115, 165), (45, 215), (115, 265)], fill=c)
    return _finish(img)


def _keyboard(c):
    img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((25, 75, 295, 245), radius=40, outline=c, width=22)
    for x in (68, 108, 148, 188, 228):
        d.rounded_rectangle((x, 112, x + 24, 136), radius=5, fill=c)
    for x in (88, 128, 168, 208):
        d.rounded_rectangle((x, 152, x + 24, 176), radius=5, fill=c)
    d.rounded_rectangle((100, 192, 220, 212), radius=8, fill=c)
    return _finish(img)


def _gear(c):
    img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = _S / 2
    for k in range(8):
        a = math.radians(k * 45)
        d.line([(cx + 78 * math.cos(a), cy + 78 * math.sin(a)),
                (cx + 128 * math.cos(a), cy + 128 * math.sin(a))], fill=c, width=40)
    d.ellipse((cx - 92, cy - 92, cx + 92, cy + 92), outline=c, width=34)
    d.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=c)
    return _finish(img)


def _info(c):
    img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((35, 35, 285, 285), outline=c, width=22)
    d.ellipse((145, 90, 175, 120), fill=c)
    d.rounded_rectangle((144, 142, 176, 235), radius=12, fill=c)
    return _finish(img)


_DRAW = {"rules": _swap, "keyboards": _keyboard, "settings": _gear, "about": _info}


def nav_icon(name, color):
    return _DRAW[name](color)
