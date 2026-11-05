"""Render docs/demo.gif from the SAME KFDemo.render(t) the website uses.
Usage: python make_gif.py   (needs playwright + chromium + Pillow)"""
import io, os
from PIL import Image
from playwright.sync_api import sync_playwright

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, "..", "..", "website"))
out = os.path.abspath(os.path.join(here, "..", "demo.gif"))
FPS = 12

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 800, "height": 700}, device_scale_factor=1)
    ctx.add_init_script("try{localStorage.setItem('theme','dark')}catch(e){}")
    page = ctx.new_page()
    page.goto("file://%s/index.html?capture" % root)
    page.add_style_tag(content=(
        "nav,section,footer,.hero>.wrap>*:not(#anim){display:none!important}"
        ".hero{background:var(--bg)!important;padding:0!important}"
        ".anim{margin:0!important;padding:12px;background:var(--bg)}"
        ".anim .win{box-shadow:none}"))
    dur = page.evaluate("KFDemo.duration")
    el = page.locator("#anim")
    frames = []
    for i in range(int(dur * FPS)):
        page.evaluate("t=>KFDemo.render(t)", i / FPS)
        frames.append(el.screenshot())
    b.close()

# merge identical consecutive frames into one longer frame
merged = []
for png in frames:
    if merged and merged[-1][0] == png:
        merged[-1][1] += 1
    else:
        merged.append([png, 1])
print("frames:", len(frames), "distinct runs:", len(merged))

imgs = [Image.open(io.BytesIO(m[0])).convert("RGB") for m in merged]
w, h = imgs[0].size
# one shared palette, built from a few representative frames
sample = Image.new("RGB", (w, h * min(6, len(imgs))))
for k, idx in enumerate(range(0, len(imgs), max(1, len(imgs) // 6))[:6]):
    sample.paste(imgs[idx], (0, k * h))
pal = sample.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
frames_p = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
durations = [int(round(m[1] * 1000 / FPS)) for m in merged]
frames_p[0].save(out, save_all=True, append_images=frames_p[1:], duration=durations, loop=0,
                 optimize=True, disposal=1)
print("wrote", out, os.path.getsize(out) // 1024, "KB", (w, h))
