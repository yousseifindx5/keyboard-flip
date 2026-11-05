"""Screenshot the website pages (used to check layout). Usage: python shots.py OUT_DIR"""
import sys, os
from playwright.sync_api import sync_playwright

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "website"))
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
pages = {"en": "index.html", "ar": "ar/index.html", "en_cl": "changelog.html", "ar_cl": "ar/changelog.html"}
jobs = [("en", 1280, "dark"), ("en", 390, "dark"), ("en", 390, "light"), ("ar", 1280, "dark"),
        ("ar", 390, "dark"), ("ar", 390, "light"), ("en_cl", 390, "dark"), ("ar_cl", 390, "dark")]
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, theme in jobs:
        ctx = b.new_context(viewport={"width": w, "height": 900})
        ctx.add_init_script("try{localStorage.setItem('theme','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        page.goto("file://%s/%s" % (root, pages[name]))
        page.wait_for_timeout(400)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        print(name, w, theme, "horizontal overflow px:", over)
        page.screenshot(path=os.path.join(out, "%s_%d_%s.png" % (name, w, theme)), full_page=True)
        ctx.close()
    b.close()
