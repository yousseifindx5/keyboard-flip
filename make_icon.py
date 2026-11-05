"""Builds assets/icon.ico from assets/icon.png only when the ICO is missing.
To change the logo: replace assets/icon.png with a square PNG (512x512 is ideal), delete assets/icon.ico and run build.bat."""
import os
from PIL import Image

PNG, ICO = "assets/icon.png", "assets/icon.ico"
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]

os.makedirs("assets", exist_ok=True)
if not os.path.exists(PNG):
    raise SystemExit("assets/icon.png is missing")
if not os.path.exists(ICO):  # the shipped icon.ico has hand-made sharp sizes; only rebuild it if it is missing
    Image.open(PNG).convert("RGBA").resize((256, 256), Image.LANCZOS).save(ICO, sizes=SIZES)
    print("icon.ico rebuilt from icon.png")
else:
    print("icon ready")
