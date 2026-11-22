"""
Gapless loops in the running app: click spacing across the loop jump.

Opens a metronome video in the app (system Chrome, which plays H.264 / AAC),
sets a loop of exactly 4 clicks with the keyboard, plays it at 1x and 0.75x
and records what the page sends to the speakers (a tap in front of every
AudioContext's destination). With a gapless loop, the clicks keep their
spacing across the jump; a seek back to the loop start would add its gap.

Usage (in the browser-test venv; better against a test server with a copy of
the library, since opening a video may start beat detection):
  python test_gapless_loop.py http://127.0.0.1:8765 <video-id-of-a-metronome>
"""
import base64
import io
import json
import os
import sys
import urllib.request
import wave

import numpy as np
from playwright.sync_api import sync_playwright

BASE, VIDEO_ID = sys.argv[1], sys.argv[2]
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "gapless_loop.json")
CLICKS_IN_LOOP = 4

RECORDER = """
(() => {
  const Base = window.AudioContext
  window.__rec = { chunks: [] }
  window.AudioContext = class extends Base {
    constructor(options) {
      super(options)
      const real = Object.getOwnPropertyDescriptor(BaseAudioContext.prototype, 'destination').get.call(this)
      const tap = this.createGain()
      tap.connect(real)
      const recorder = this.createScriptProcessor(2048, 2, 1)
      tap.connect(recorder)
      recorder.connect(real)
      recorder.onaudioprocess = (e) => window.__rec.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      window.__rec.sampleRate = this.sampleRate
      Object.defineProperty(this, 'destination', { get: () => tap })
    }
  }
})()
"""

TAKE = """
() => {
  const r = window.__rec
  const all = new Float32Array(r.chunks.reduce((n, c) => n + c.length, 0))
  let o = 0
  for (const c of r.chunks) { all.set(c, o); o += c.length }
  r.chunks = []
  const u = new Uint8Array(all.buffer)
  let bin = ''
  for (let k = 0; k < u.length; k += 0x8000) bin += String.fromCharCode.apply(null, u.subarray(k, k + 0x8000))
  return { sr: r.sampleRate, data: btoa(bin) }
}
"""


def find_clicks(x: np.ndarray, sr: int) -> np.ndarray:
    """Onset times of loud clicks, at least 0.25 s apart."""
    env = np.abs(x)
    threshold = max(env.max() * 0.3, 1e-3)
    found, i = [], 0
    while i < len(env):
        if env[i] > threshold:
            found.append(i)
            i += int(0.25 * sr)
        else:
            i += 1
    return np.array(found) / sr


def metronome_clicks() -> np.ndarray:
    """Click times in the first 20 s, from the app's own audio endpoint."""
    url = f"{BASE}/api/library/{VIDEO_ID}/audio?start=0&end=20&sampleRate=48000"
    with urllib.request.urlopen(url) as response, wave.open(io.BytesIO(response.read())) as file:
        x = np.frombuffer(file.readframes(file.getnframes()), "<i2").reshape(-1, 2)[:, 0] / 32768
    return find_clicks(x, 48000)


def take(page) -> tuple[int, np.ndarray]:
    r = page.evaluate(TAKE)
    return r["sr"], np.frombuffer(base64.b64decode(r["data"]), np.float32)


def seek(page, t: float) -> None:
    page.evaluate(
        """(t) => new Promise((ok) => { const v = document.querySelector('video');
            v.addEventListener('seeked', ok, { once: true }); v.currentTime = t })""",
        t,
    )


def main() -> None:
    clicks = metronome_clicks()
    period = float(np.median(np.diff(clicks)))
    first = clicks[np.argmin(np.abs(clicks - 12))]
    start = first - 0.1  # a little before a click
    end = start + CLICKS_IN_LOOP * period
    results: dict = {"video": VIDEO_ID, "click_period_ms": round(period * 1000, 1), "loop": [round(start, 3), round(end, 3)]}
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(RECORDER)
        page.goto(f"{BASE}/watch/{VIDEO_ID}")
        page.wait_for_function("document.querySelector('video')?.readyState >= 2", timeout=30000)
        page.evaluate("document.querySelector('video').pause()")
        seek(page, start)
        page.keyboard.press("a")
        seek(page, end)
        page.keyboard.press("b")
        page.wait_for_timeout(1500)  # the loop's audio is fetched when A is set
        seek(page, start - 1.5)
        take(page)
        page.keyboard.press(" ")
        page.wait_for_timeout(int((1.5 + 4 * (end - start)) * 1000))
        sr, at_1x = take(page)
        for _ in range(5):
            page.keyboard.press("-")  # 0.75x
        page.wait_for_timeout(500)
        take(page)
        page.wait_for_timeout(int(4 * (end - start) / 0.75 * 1000))
        sr, at_075x = take(page)
        browser.close()
    for name, x, rate in (("1x", at_1x, 1.0), ("0.75x", at_075x, 0.75)):
        intervals = np.diff(find_clicks(x, sr)) * 1000
        error = intervals - period * 1000 / rate
        results[name] = {
            "intervals_ms": [round(float(d), 1) for d in intervals],
            "max_error_ms": round(float(np.abs(error).max()), 1),
        }
    results["errors"] = errors
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    with open(RESULTS, "w") as file:
        json.dump(results, file, indent=1)
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
