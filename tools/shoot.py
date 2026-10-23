#!/usr/bin/env python3
"""Render a dashboard file headless: screenshots + console errors. Usage: shoot.py FILE OUTDIR [prefix]"""
import os, sys
from playwright.sync_api import sync_playwright

src, outdir = sys.argv[1], sys.argv[2]
prefix = sys.argv[3] if len(sys.argv) > 3 else "shot"
os.makedirs(outdir, exist_ok=True)
proxy = os.environ.get("HTTPS_PROXY")
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(proxy={"server": proxy} if proxy else None)
    for name, vp, scheme, mobile in [
        ("desktop-light", {"width": 1280, "height": 900}, "light", False),
        ("desktop-dark", {"width": 1280, "height": 900}, "dark", False),
        ("mobile-light", {"width": 390, "height": 844}, "light", True),
        ("mobile-dark", {"width": 390, "height": 844}, "dark", True),
    ]:
        ctx = b.new_context(viewport=vp, color_scheme=scheme, device_scale_factor=2 if mobile else 1,
                            is_mobile=mobile, has_touch=mobile)
        page = ctx.new_page()
        page.on("console", lambda m, n=name: errors.append((n, m.type, m.text)) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e, n=name: errors.append((n, "pageerror", str(e))))
        page.goto("file://" + os.path.abspath(src))
        page.wait_for_timeout(1200)
        sw = page.evaluate("document.documentElement.scrollWidth")
        cw = page.evaluate("document.documentElement.clientWidth")
        if sw > cw:
            errors.append((name, "overflow", "page scrolls horizontally: %s > %s" % (sw, cw)))
        page.screenshot(path=os.path.join(outdir, "%s-%s.png" % (prefix, name)), full_page=True)
        ctx.close()
    b.close()
for e in errors:
    print(*e)
print("done, %d issues" % len(errors))
