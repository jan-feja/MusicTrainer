"""Run the browser-side tests in headless Chromium (Playwright).

Serves experiments/browser/ at /  and  MT_DATA at /data/, opens each test
page, waits for it to set window.__result and stores it in results/.

Usage (in a venv with playwright installed):
  python run_browser_tests.py [stretch] [alphatab] [essentia]
"""
import functools
import http.server
import json
import os
import sys
import threading

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ["MT_DATA"]
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?")[0]
        if path.startswith("/data/"):
            return os.path.join(DATA, *path[len("/data/"):].split("/"))
        return os.path.join(HERE, "browser", *path.lstrip("/").split("/"))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        # needed for SharedArrayBuffer-based libraries
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        super().end_headers()

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run_page(browser, port, name, timeout_s=600):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
    page.goto(f"http://127.0.0.1:{port}/{name}.html")
    try:
        page.wait_for_function("window.__result !== undefined", timeout=timeout_s * 1000)
        result = page.evaluate("window.__result")
    except Exception as e:
        result = {"error": f"timeout or failure: {e}"}
    result["console"] = logs[-40:]
    page.screenshot(path=os.path.join(RESULTS, f"browser_{name}.png"), full_page=False)
    with open(os.path.join(RESULTS, f"browser_{name}.json"), "w") as f:
        json.dump(result, f, indent=1)
    page.close()
    return result


if __name__ == "__main__":
    tests = sys.argv[1:] or ["stretch", "alphatab", "essentia"]
    srv = serve()
    port = srv.server_address[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        for t in tests:
            r = run_page(browser, port, t)
            print(f"===== {t}")
            print(json.dumps({k: v for k, v in r.items() if k != "console"}, indent=1)[:4000])
            errs = [l for l in r.get("console", []) if "error" in l.lower()]
            if errs:
                print("console errors:", *errs[:10], sep="\n  ")
        browser.close()
    srv.shutdown()
