"""Screenshot a Guitar Pro / MusicXML file as alphaTab renders it (all tracks).

Usage (venv with playwright): python render_notation.py <file under MT_DATA> <out.png> [bars]
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

from run_browser_tests import DATA, serve


def main() -> None:
    rel = os.path.relpath(sys.argv[1], DATA).replace(os.sep, "/")
    bars = sys.argv[3] if len(sys.argv) > 3 else "8"
    srv = serve()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/notation.html?file=/data/{rel}&bars={bars}")
        page.wait_for_function("window.__result !== undefined", timeout=120_000)
        print(json.dumps(page.evaluate("window.__result")))
        page.screenshot(path=sys.argv[2], full_page=True)
        errors = [line for line in logs if "error" in line.lower()]
        if errors:
            print("\n".join(errors[:10]))
        browser.close()


if __name__ == "__main__":
    main()
