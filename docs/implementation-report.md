### Implementation report: how to build each feature
Tested on 15 November 2026 on a Windows laptop (Ryzen 7 5800H, 32 GB RAM, RTX 3060 Laptop GPU 6 GB). Scripts, raw numbers and setup steps are in [experiments/](../experiments/).

---

#### TL;DR
- **Recommended stack:** a browser UI (TypeScript) talking to a local Python server (FastAPI). Python downloads songs and runs all analysis once per song. The browser does everything real-time: speed, pitch, loops, mute/solo, notation. Both can later be wrapped into a desktop app (Tauri or Electron with the Python server bundled).
- **Ready to build (tested, works well):** YouTube download, speed change, pitch shift, mute/solo, BPM + beats + bar starts, beat-synced loops, separating drums / bass / vocals, tuning and key detection, showing imported tabs and scores.
- **Works, but needs extra work:**
  - guitar stem (OK) and piano stem (fails)
  - chords on real songs (jumpy)
  - recording (needs a latency calibration step)
  - lining up imported tabs with the recording (good on average, some bad spots)
- **Where most time would go (research-level):**
  - turning audio into readable notes / tabs
  - automatic scoring of the user's take
  - verse / chorus detection
- **Lessons from testing:**
  - 2 of 10 YouTube links failed (region lock, deleted video).
  - The Beat This! model server refused downloads ("rate limited"), so the app should ship model files.
  - On battery, the laptop GPU was throttled to the point of hanging, so everything must also run on the CPU. It does, at acceptable speed.

---

#### Features sorted by effort
Effort for one person who knows the stack: **XS** < 1 day, **S** 1–2 days, **M** 3–5 days, **L** 1–2 weeks, **XL** several weeks / research. Efforts are for each feature on top of a basic project skeleton (row 0).
Status: ✅ tested and works · ⚠️ works with caveats · 🔬 needs research

| # | Feature | Effort | Status | Recommended way | Key test result |
|---|---|---|---|---|---|
| 0 | Project skeleton: server, job queue, song library, UI shell, audio graph | M | ✅ | FastAPI + SQLite; Web Audio | no technical risk |
| 1 | Mute / solo / volume per track | XS | ✅ | Web Audio gain node per stem | part of the tested audio graph |
| 2 | Pitch shift / transpose | S | ✅ | Signalsmith Stretch (`semitones`) | +2 semitones measured as +200 cents exactly |
| 3 | Playback speed (%) | S | ✅ | Web Audio `playbackRate` + one Signalsmith node | 6 stems at 0.75×: runs 20× faster than real time, pitch and length exact |
| 4 | Tuning detection | S | ✅ | librosa `estimate_tuning` | within 4 cents (−35 cents read as −36) |
| 5 | Key detection | S | ⚠️ | madmom or librosa | sometimes gives the relative / parallel key; 2 methods agree on 6 of 8 real songs |
| 6 | YouTube download + storage | S | ✅ | yt-dlp + Deno, ffmpeg | ~14 s per song; 2 of 10 links unavailable |
| 7 | BPM, beats, bar starts | S | ✅ | Beat This! | real songs: beats 0.84, bar starts 0.80, BPM right on 8 of 8; 1.2 s per song on GPU, 12 s on CPU |
| 8 | Speed set in BPM | XS | ✅ | rate = target BPM / song BPM | needs 3 and 7 |
| 9 | Beat-synced loops | M | ✅ | snap to the beat grid; Web Audio loop points | as good as 7: bar starts right ~80 % of the time |
| 10 | Track separation | M | ✅ / ⚠️ | Demucs `htdemucs_6s`, background job, cached | real music: vocals 8.7, drums 9.5, bass 9.0 dB; guitar 8.1 dB, piano 0.3 dB; 11 s per song on GPU, ~2 min on CPU |
| 11 | Show / import tabs and scores | M | ✅ | alphaTab | Guitar Pro 5, Guitar Pro 8 (with recording + sync points) and MusicXML load and render; player speed and loop work |
| 12 | Chords on a timeline | M | ⚠️ | madmom CNN + CRF | synthetic song 95–98 % right; real songs jumpy |
| 13 | Record + compare by ear | M | ⚠️ | getUserMedia + AudioWorklet + calibration | browser-reported latency is unreliable; needs a click-test calibration |
| 14 | Progress and practice plan | M | ✅ | app logic + SQLite | no technical risk |
| 15 | Align imported notation with the recording | L | ⚠️ | synctoolbox → alphaTab sync points | typical error 20 ms, 96–98 % of beats within 100 ms, a few big misses |
| 16 | Auto-detect song sections | L | 🔬 | allin1 (Linux / WSL), manual markers first | simple method finds only a third of section starts (±3 s) |
| 17 | Notes / tabs from audio | XL | 🔬 | Basic Pitch / ADTOF + fret choice + notation cleanup | clean stems: piano 0.96, guitar 0.60, bass 0.58; piano from a separated stem 0.22 |
| 18 | Automatic score of a take | XL | 🔬 | calibrated latency + Demucs on the take + Basic Pitch + note matching | simulated take: all 22 wrong notes found, timing within ~10 ms, but only with a clean recording or cleanup; real instruments untested |

---

#### Recommended architecture

```
Browser UI (TypeScript)                          Local Python server (FastAPI)
- Web Audio: stems -> gain (mute/solo)           - yt-dlp + Deno: download audio / video
    -> ONE Signalsmith node (speed, pitch)       - ffmpeg: convert
    -> speakers; loops via loopStart/loopEnd     - Demucs: stems (background job, cached)
- <video muted>, kept in sync with the audio     - Beat This!: BPM, beats, bar starts
- wavesurfer.js: waveform, beat grid, loops      - madmom / librosa: key, chords, tuning
- alphaTab: tabs / scores, sync points           - synctoolbox: align notation
- getUserMedia + AudioWorklet: recording         - Basic Pitch / ADTOF: notes from audio
                                                 - SQLite: library, loops, practice log
                <---- HTTP: audio files + analysis.json ---->
```

**Why this split**
- Downloading and all the machine-learning models are Python libraries.
- The best tools for the real-time and visual parts are web libraries: alphaTab (the only good open-source tab renderer with a player), Signalsmith Stretch (real-time speed / pitch) and wavesurfer.js.
- Pre-rendering speed changes in Python is too slow. Rubber Band took 119 s to re-render 6 stems of a 2.5-minute song at 0.75× speed. The browser does the same live, using about 5 % of one core.
- It fits the 3-person split in [functionalities.md](functionalities.md): import + separation and beat analysis are server-side, the player is browser-side.

**Design rules found while testing**
- **Put the mixer before the speed changer.**
  1. Play the stems slower with Web Audio's built-in `playbackRate`; this lowers their pitch.
  2. Mix them through the per-stem gain nodes (this is mute / solo).
  3. Send the mix through a single Signalsmith node that shifts the pitch back up, plus any transpose.

  One speed changer serves any number of stems. That setup ran 20× faster than real time; one speed changer per stem managed only 3×.
- **Memory:** 6 decoded stereo stems of a 4-minute song take ~500 MB in the browser. If that becomes a problem, use mono stems for instruments or load stems on demand.
- **Run each ML tool as a separate job / process.** Their dependencies clash: the BS-RoFormer separator package would downgrade a library Beat This! needs, and Basic Pitch pulls in TensorFlow.
- **Ship model files with the app** instead of downloading them on first use.
- **Everything must work without a GPU.** CPU times per 4-minute song: separation ~2 min, beats 12 s, key / chords under a minute.

---

#### How each technology option would implement the features

| Feature | A. Browser UI + Python server (recommended) | B. Python desktop app (Qt) | C. Browser only, no server |
|---|---|---|---|
| YouTube download | yt-dlp on the server | yt-dlp inside the app | not possible (browsers can't fetch YouTube media); user uploads files |
| Speed / pitch | Signalsmith in Web Audio (tested) | pre-render with Rubber Band (tested: ~2 min per speed change) or a real-time stretcher in an audio callback (fragile in Python) | same as A |
| Mute / solo | gain nodes | mix arrays in the audio callback | gain nodes |
| BPM / beats | Beat This! on the server (tested) | same, in-process | essentia.js (tested: beats 0.89 on synthetic, no bar starts) |
| Loops | Web Audio loop points | own playback buffer logic | same as A |
| Separation | Demucs on the server (tested) | same | browser ports of Demucs exist (not tested; slow, memory-heavy) |
| Key / chords / tuning | madmom / librosa (tested) | same | essentia.js (tested; chords fail on detuned songs) |
| Show / import tabs | alphaTab (tested) | alphaTab inside a web view anyway | alphaTab |
| Align notation | synctoolbox (tested) → alphaTab sync points | same | no ready library |
| Notes from audio | Basic Pitch (tested) | same | Basic Pitch also has a TypeScript version |
| Record / score | getUserMedia + server analysis | sounddevice (lower latency, ASIO drivers) | recording yes, scoring hard |
| Sections | server (allin1 needs Linux / WSL) | same | – |
| Progress / plan | SQLite on the server | SQLite | IndexedDB |
| **Verdict** | **best fit** | one language, but weaker real-time audio, and notation still needs a web view | demo only |

A native C++ app (e.g. JUCE) would give the lowest audio latency, but the ML models and tab rendering would have to be ported. That's far too much work for this project.

---

#### Feature details (in effort order)

##### 1. Mute / solo / volume (XS, ✅)
- **Build:** one gain node per stem; solo sets the others to 0. Place the gains before the speed changer (see architecture).
- **Tested:** part of the speed-change audio graph below; no issues.

##### 2–3. Playback speed and pitch shift (S, ✅)
- **Build:** [Signalsmith Stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch) (MIT, runs as WebAssembly in an AudioWorklet). For speed `r`, the stems get `playbackRate = r` and the Signalsmith node gets `semitones = −12·log2(r) + transpose`.
- **Alternatives:** SoundTouchJS (half as fast), or `<audio>` with `preservesPitch`. That one is built into browsers (confirmed in Chromium), but 6 separate `<audio>` elements drift apart.
- **Tested** in headless Chromium, 6 stems, 30 s of audio at 0.75×:

  | Setup | Speed vs real time | 440 Hz test tone after | Output length |
  |---|---|---|---|
  | 1 Signalsmith node after the mixer | 20.4× | 440 Hz | exact |
  | 1 SoundTouch node after the mixer | 10.0× | 440 Hz | exact |
  | 6 Signalsmith nodes (one per stem) | 3.1× | 440 Hz | exact |

- **Python, offline, for comparison:** Rubber Band (via pedalboard) took 119 s and librosa 26 s (lower quality) for 6 stems × 148 s. Pitch was exact in both, and +2 semitones measured exactly +200 cents.
- **Still to do:**
  - Listen to the quality at 50–70 % speed. Signalsmith says it sounds best between 0.75× and 1.5×.
  - Compare it with SoundTouch by ear.

##### 4. Tuning detection (S, ✅)
- **Build:** `librosa.estimate_tuning` on the mix. Show "this recording is X cents flat" and offer to shift it to A440 using feature 2.
- **Tested:**
  - The 35-cents-flat song read −36. Real songs shifted by −30 / +20 cents came back within 4 cents of the shift.
  - essentia.js (browser) was also exact on the synthetic song (431.2 Hz). On one real song it said −24 cents where librosa said −2.
- **Limit:** Eb tuning (everything a whole semitone down) can't be told apart from a song in a different key. Let the user set "my guitar is tuned to Eb" and transpose by −1.

##### 5. Key detection (S, ⚠️)
- **Build:** madmom `CNNKeyRecognitionProcessor`, librosa chroma + key profiles, or essentia.js `KeyExtractor`.
- **Tested:**
  - On the synthetic song (Em–C–G–D, meant as E minor), all three methods said G major. G major uses the same notes, so that's musically defensible.
  - On the real songs there's no answer key. The two Python methods agreed on 6 of 8; the disagreements were relative / parallel keys (e.g. D major vs D minor).
- **Still to do:** show the two best candidates and let the user correct them.

##### 6. YouTube download (S, ✅)
- **Build:** [yt-dlp](https://github.com/yt-dlp/yt-dlp) on the server, plus [Deno](https://deno.com). Since late 2025 yt-dlp needs a JavaScript runtime for YouTube; without one it still worked here, with a warning that formats may be missing.
  - Audio: `-f bestaudio -x --audio-format wav`.
  - Video: request H.264 + AAC (`-S vcodec:h264,acodec:m4a`). The default gave AV1 video + Opus audio, which not every player handles.
- **Tested:** 8 of 10 songs downloaded in ~14 s each, including WAV conversion. A 720p video with audio merged in 15 s. Failures: one video is only available in the US, and one was deleted with its channel.
- **Still to do:**
  - clear error messages for unavailable videos
  - updating yt-dlp regularly (YouTube changes break it every few weeks)
  - importing local files as well
- **Note:** downloading from YouTube is against YouTube's terms of service. For a personal practice tool it's a grey area, but the app shouldn't be published as a downloader.

##### 7–8. BPM, beats and bar starts (S, ✅)
- **Build:** [Beat This!](https://github.com/CPJKU/beat_this) (MIT) on the server writes beats and bar starts into `analysis.json`. BPM = 60 / median beat gap. Speed in BPM = target BPM / song BPM.
- **Tested** on 8 real songs with human annotations and on 2 synthetic songs (steady tempo, tempo drifting ±8 %):

  | Method | Beats (real) | Bar starts (real) | BPM right (real) | Synthetic: beats / bar starts | Time per song |
  |---|---|---|---|---|---|
  | **Beat This!** | 0.84 | **0.80** | 8 / 8 | 1.00 / 0.95–1.00 | 1.2 s GPU, 12 s CPU |
  | madmom | 0.84 | 0.77 | 8 / 8 | 1.00 / 0.99 | 52 s CPU |
  | librosa | 0.81 | – | 8 / 8 | 0.86 / – | 1 s |
  | essentia.js (browser) | – | – | – | 0.89–0.90 / – | 15 s |

  Scores are F-measures: the share of beats found within ±70 ms, with false alarms counted against. Real-song scores are a lower bound, because the YouTube audio had to be re-aligned automatically to annotations that were made on CD audio.
- Bar-start scores per song ranged from 0.56 to 0.98. The errors are mostly the bar starting one beat too early or late.
- **Still to do:**
  - A "fix the beat grid" UI (move the bar start by one beat, tap tempo). The commercial apps that let you correct analysis do exactly this.
  - Ship the model file with the app. The official download server answered "rate limited" during testing; a mirror on Hugging Face worked.
- **Follow-up (21 November 2026), now implemented:**
  - **Distribution:** the official server works again, and Beat This! is on PyPI (`beat-this` 1.1, MIT for code and weights).
  - **Model choice:** `final0` and `small0` were equally accurate on real songs: beats 0.86 / 0.85, bar starts 0.82 / 0.81. `small0` is 40 % faster (1.4 vs 2.2 s of CPU per minute of audio).
  - **Timing:** detected beats sit a steady ~20 ms after sharp attacks (spread under 2 ms on synthetic songs). The player compensates by jumping 30 ms early.
  - **Other checks:** a song without drums still worked (0.98); AAC input gave the same beats as WAV.
  - **Loops:** on real songs, both ends of a 1-, 2- or 4-bar loop landed on the true bar lines 86–88 % of the time. The misses come from soft intros without drums; once the band plays, it scores 0.97–0.99.
  - **Details:** [../experiments/test_beats_followup.py](../experiments/test_beats_followup.py).
- **Second follow-up (22 November 2026), now implemented:** Beat This!'s peak picking let bars have any length (20 % odd bars in a real song). The app now decodes the network output into a grid with steady bars, and the user can fix tempo octave, meter and bar starts. Tested on real held-out music (GTZAN) and on test songs written as scores: [beat-tracking.md](beat-tracking.md).
- **Third follow-up (22 November 2026), now implemented: gapless loops.** Jumping the `<video>` back to the loop start left 5–190 ms of silence (the media pipeline restarts; an audio-only element was no faster). The loop's sound now comes from Web Audio, as planned for the stems:
  - **Audio:** the backend cuts the audio around the loop with ffmpeg and sends it as WAV (`/api/library/<id>/audio`). The cut matches Chrome's own decoding sample for sample. Decoding the whole file in the browser instead took 1.8 s and 130 MB for a 6-minute song, too much for long lesson videos.
  - **Playback:** one Signalsmith Stretch node with its built-in loop points. Offline at 1×, its output matched the original closely (spectral error 0.053 vs 0.036 for the original shifted by 1 ms), with no level dip at the wrap and no drift over passes.
  - **In the app:** click spacing across the jump stays exact (600.0 ± 0.1 ms at 100 BPM; ±2 ms at 0.75×, the stretcher's transient jitter). The video follows muted.

##### 9. Beat-synced loops (M, ✅)
- **Build:**
  - Snap loop start / end to the nearest beat or bar start from feature 7.
  - Play with `AudioBufferSourceNode.loop` / `loopStart` / `loopEnd`. These are sample-accurate, so giving every stem the same values keeps them in sync.
  - Count-in: schedule metronome clicks on the beat grid before the loop starts.
  - Save loops per song.
- **Tested:** only through feature 7. Bar starts are right ~80 % of the time, so add "move loop by one beat / bar" buttons.

##### 10. Track separation (M, ✅ / ⚠️)
- **Build:** [Demucs](https://github.com/adefossez/demucs) (MIT). The original Facebook repository is archived; this is the maintained fork by the same author. Use `htdemucs_6s` (drums, bass, vocals, guitar, piano, other), run it as a background job after import, and cache the stems.
- **Tested quality** (SDR in dB, higher = cleaner; ~5–7 is usable for practice, above 9 is very clean):

  | Model | Vocals | Drums | Bass | Other | Guitar* | Piano* |
  |---|---|---|---|---|---|---|
  | htdemucs | 8.7 | 9.5 | 9.0 | 5.2 | – | – |
  | htdemucs_ft | 8.4 | 9.8 | 9.2 | 5.2 | – | – |
  | htdemucs_6s | 8.6 | 9.3 | 8.2 | 4.8 | 8.1 | 0.3 |

  Median over 50 real MUSDB18 clips. *Guitar and piano were measured on the synthetic song, because MUSDB18 has no such tracks.
- **Speed** for a 4:14 song: 11–13 s on the GPU (htdemucs_ft: 50 s), ~2 min on the CPU (2.1× real time).
- **Problems:**
  - The piano stem basically fails.
  - Guitar is fine on a single distorted rhythm guitar but untested on songs with several guitars.
  - Stronger models exist: BS-RoFormer is ~1.3 dB better in one 2026 benchmark. Its Python package clashed with Beat This!'s dependencies, so I didn't test it.
- **Implemented (22 November 2026):** `htdemucs_6s` in a worker process, queued after each download (the song open in the player first), stems stored as FLAC. The player mixes them as in the architecture above, with mute, solo (one stem) and volume per stem, and a waveform lane each.

##### 11. Show / import tabs and scores (M, ✅)
- **Build:** [alphaTab](https://alphatab.net) (MPL-2.0). It renders Guitar Pro 3–8 and MusicXML as tab + notation. It has its own player with speed, loop range and a playback cursor, and can follow a real recording via sync points; Guitar Pro 8 files can carry the recording inside.
- **Tested** in headless Chromium ([screenshot](../experiments/results/browser_alphatab.png)):
  - Our generated Guitar Pro 5 bass tab (52 bars) rendered in 0.45 s, and the player ran at 0.75× in a 2-bar loop.
  - A Guitar Pro 8 file with an embedded recording and 16 sync points parsed and rendered.
  - MusicXML rendered.
- **Not verified:** playback of the embedded recording, because the headless browser blocked media playback. Check it in a normal browser.
- **Where to get files:**
  - The user's own Guitar Pro / MusicXML / MIDI files.
  - There are no public tab APIs. Songsterr's unofficial API reportedly stopped working in 2026, Ultimate Guitar has none, and scraping breaks their terms.
  - The [Lakh MIDI Dataset](https://colinraffel.com/projects/lmd/) (176k MIDI files, 45k matched to known songs, CC-BY) is an option, but quality varies.

##### 12. Chords on a timeline (M, ⚠️)
- **Build:** madmom `CNNChordFeatureProcessor` + `CRFChordRecognitionProcessor` (major / minor chords) on the server. Snap chord changes to beats and draw them on the waveform.
- **Tested** on the synthetic song (share of time with the right chord):

  | Method | Normal | Tempo drift | 35 cents flat | Eb |
  |---|---|---|---|---|
  | librosa templates + smoothing | 98 % | 98 % | 97 % | 98 % |
  | madmom CNN + CRF | 96 % | 96 % | 95 % | 96 % |
  | essentia.js (browser) | 92 % | 92 % | **0 %** | – |

- On a real song both Python methods give plausible but jumpy sequences: many very short chords and major / minor flips. The synthetic song is much easier than real recordings; for comparison, the autochord project reports 67 % on real songs.
- **Still to do:**
  - one chord per beat or bar, dropping very short chords
  - a "simple chords" mode
  - letting the user edit chords
  - correcting for tuning first (essentia.js failed completely on the detuned song)
- **Implemented (22 November 2026):** librosa templates (no madmom), averaged per beat and smoothed with a Viterbi pass, so chords change only on beats; on the pitched stems once they exist. Shown in a lane under the timeline. Still major / minor only, and not editable.

##### 13. Record and compare by ear (M, ⚠️)
- **Build:** `getUserMedia` with echo cancellation, noise suppression and auto gain turned off, plus an AudioWorklet recorder. Store the takes, and play a take together with the song, shifted by the latency.
- **Latency:** browsers report wrong values. Reports say `outputLatency` is too low or fixed; measured end-to-end latency is ~55–70 ms in Chrome and Firefox. So measure it once with a calibration: play clicks, record them (mic near the speaker, or a loopback cable), and use the measured delay.
- **Tested** in simulation:
  - With a clean recording, the delay estimated from the take itself was 140 ms against a true 137 ms.
  - With the song also reaching the mic from the speakers, that self-estimate failed (−160 ms). So calibration is needed.

##### 14. Progress and practice plan (M, ✅)
- Plain app logic: SQLite tables for practice sessions, loops, best clean speed per loop and notes. No technical risk, nothing to test.

##### 15. Align imported notation with the recording (L, ⚠️)
- **Build:**
  1. Take the notation's notes as MIDI.
  2. Run synctoolbox (chroma + onset features, multi-scale DTW) against the recording.
  3. Turn the result into sync points (bar → time) for alphaTab.

  Shortcut when the bar counts match: bar k = the k-th detected bar start.
- **Tested:** a score at a steady 100 BPM against recordings with drifting tempo, 35 cents flat, and in Eb:

  | Method | Typical error | Beats within 100 ms | Notes |
  |---|---|---|---|
  | **synctoolbox** | 20–22 ms | 96–98 % | a few big misses push the average to ~140 ms |
  | bar k = k-th detected bar start | 17–20 ms | 94–100 % | only if the notation has exactly the song's bars |
  | librosa chroma DTW | 40–62 ms | 79–83 % | unreliable |

- **Still to do:**
  - repeats and edits (e.g. the tab has 2 choruses, the recording 3)
  - the misses at the start and end
  - a manual sync editor (alphaTab's online Media Sync Editor shows what the UI could look like)

##### 16. Song sections (L, 🔬)
- **Follow-up (23 November 2026):** measured in depth in [transcription-and-sections.md](transcription-and-sections.md).
- **Tested:** librosa Laplacian segmentation on the Beat This! beat grid, on 8 real songs:
  - section starts found within 0.5 s: 10–14 %
  - section starts found within 3 s: 32 %
  - grouping of repeated parts (pairwise F): 0.50

  Not usable as it is.
- **Option:** [allin1](https://github.com/mir-aidj/all-in-one) (MIT, trained on the Harmonix Set; labels intro / verse / chorus / bridge / solo / …, plus beats). It needs NATTEN, which has no ready Windows build, so it would run on Linux / WSL / Docker. Not tested.
- **Plan:** manual section markers first (snapped to bars), automatic detection later.

##### 17. Notes / tabs from audio (XL, 🔬)
- **Follow-up (23 November 2026):** measured in depth in [transcription-and-sections.md](transcription-and-sections.md).
- **Build:**
  1. Separate the song (feature 10).
  2. Transcribe the stem: [Basic Pitch](https://github.com/spotify/basic-pitch) (Apache-2.0) for pitched instruments, ADTOF (CC BY-NC-SA) for drums.
  3. Quantise the notes to the beat grid.
  4. Choose strings and frets.
  5. Display with alphaTab.
- **Tested** on the synthetic song (note F-measure: right pitch, onset within 50 ms):

  | Stem | From the true stem | From the Demucs stem |
  |---|---|---|
  | Piano | 0.96 | 0.22 |
  | Melody (synth voice) | 0.95 | 0.10 |
  | Guitar (strummed chords) | 0.60 | 0.65 |
  | Bass | 0.58 | 0.53 |
  | Drums (ADTOF, per drum) | 0.98–1.00 | 0.94–1.00 |

  - Bass loses points to many extra short notes (precision 0.43), so it needs cleanup: a minimum note length, one note at a time.
  - Piano and melody fail on separated stems because their separation failed.
  - Drums are near-perfect, but synthetic drums are easy; the ADTOF authors report F ≈ 0.88 on real recordings.
- **Notes → readable notation is a separate problem:**
  - music21's direct MIDI → MusicXML conversion gave messy rhythms and lost the tempo and track names ([screenshot](../experiments/results/browser_alphatab.png)).
  - Our simple fret rule produced a correct bass tab. Guitar chords need a real fingering search.
- Commercial apps (Klangio, Songscription) do this as their whole product.

##### 18. Automatic score of a take (XL, 🔬)
- **Build:**
  1. Correct for the calibrated latency.
  2. Optionally run Demucs on the take to remove the song bleeding in from the speakers.
  3. Transcribe the take with Basic Pitch.
  4. Match the notes to the reference part (±100 ms, same pitch).
  5. Report wrong and missed notes, and timing per bar.
- **Tested** on a simulated bass take with known mistakes: 22 wrong and 18 missed out of 384 notes, 137 ms latency, 4 rushed bars:

  | Recording | Wrong notes found (precision / recall) | Missed notes (precision / recall) | Timing error |
  |---|---|---|---|
  | Plugged in / headphones | 1.00 / 1.00 | 0.95 / 1.00 | 9 ms |
  | Mic + song from speakers | fails: latency estimate wrong | – | – |
  | Mic + speakers, calibrated latency | 0.63 / 1.00 | 0.67 / 0.44 | 23 ms |
  | Mic + speakers, calibrated + Demucs on the take | 1.00 / 1.00 | 0.78 / 1.00 | 11 ms |

- Rushing detection is weak: it flagged 1 of the 4 rushed bars.
- **Big caveat:** all of this is synthetic. Real playing (bends, slides, muted notes, chords) will be much harder.
- **Easiest realistic start:** a MIDI keyboard or e-drums via the browser's Web MIDI API (no transcription needed), or bass (single notes).

---

#### Licences (matter only if the app is published)
- **MIT:** Demucs, Beat This!, Signalsmith Stretch, synctoolbox, allin1
- **Apache-2.0:** Basic Pitch
- **MPL-2.0:** alphaTab, SoundTouchJS
- **GPL-3.0:** pedalboard / Rubber Band
- **AGPL-3.0:** essentia.js
- **Non-commercial (CC BY-NC-SA):** madmom's model files, ADTOF
- **Unlicense:** yt-dlp

---

#### Test setup
- **Machine:** Windows 10, Ryzen 7 5800H (8 cores), 32 GB RAM, RTX 3060 Laptop GPU 6 GB, Python 3.11, PyTorch 2.5.1, headless Chromium (Playwright).
- **Data:**
  - A synthetic 52-bar band song rendered with FluidSynth in 4 versions (steady, tempo drifting ±8 %, 35 cents flat, Eb), with exact answers for beats, chords, key, sections, notes and separate instrument tracks.
  - 8 real songs from the [Harmonix Set](https://github.com/urinieto/harmonixset): YouTube audio plus human beat and section annotations.
  - 50 MUSDB18 7-second previews with their true stems.
- **Caveats:**
  - Synthetic audio is easier than real recordings, so treat those numbers as a best case.
  - The Harmonix annotations were made on CD audio. I re-aligned the YouTube versions automatically (start of the music, then onsets, then chord changes to find the bar start), not by hand.
  - The GPU numbers were measured on mains power; on battery the GPU was too throttled to use.
- **Reproduce:** see [experiments/README.md](../experiments/README.md).

---

#### Sources
- yt-dlp needs a JavaScript runtime: https://github.com/yt-dlp/yt-dlp/issues/15012 , https://www.gigazine.net/gsc_news/en/20251113-yt-dlp-required-deno-javascript-runtime
- Demucs (maintained fork): https://github.com/adefossez/demucs
- Separation benchmark incl. BS-RoFormer: https://aistemsplitter.org/blog/htdemucs-vs-bs-roformer-vs-spleeter-2026-benchmark , https://arxiv.org/pdf/2309.02612
- Beat This!: https://github.com/CPJKU/beat_this , paper https://arxiv.org/pdf/2407.21658 ; weights mirror https://huggingface.co/safe-models/beat-this-final0
- madmom: https://github.com/CPJKU/madmom
- allin1: https://github.com/mir-aidj/all-in-one
- Signalsmith Stretch (web): https://www.npmjs.com/package/signalsmith-stretch
- SoundTouchJS AudioWorklet: https://www.npmjs.com/package/@soundtouchjs/audio-worklet
- alphaTab audio / video sync: https://alphatab.net/docs/guides/audio-video-sync , Media Sync Editor: https://alphatab.net/docs/guides/media-sync-editor
- essentia.js: https://github.com/MTG/essentia.js
- synctoolbox: https://github.com/meinardmueller/synctoolbox
- Basic Pitch: https://github.com/spotify/basic-pitch
- ADTOF and its PyTorch port: https://github.com/MZehren/ADTOF , https://github.com/xavriley/ADTOF-pytorch
- autochord (chord recognition accuracy): https://pypi.org/project/autochord
- Browser audio latency measurements: https://www.jefftk.com/p/browser-audio-latency , https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/media/latency_tracing.md
- Songsterr unofficial API status: https://www.npmjs.com/package/songsterr , https://publicapi.dev/songsterr-api
- Lakh MIDI Dataset: https://colinraffel.com/projects/lmd/
- MIDI to tab: https://arxiv.org/html/2408.05024v1 , tayuya https://git.vipul.xyz/github-mirrors/tayuya
- Harmonix Set: https://github.com/urinieto/harmonixset ; MUSDB18: https://sigsep.github.io/datasets/musdb.html
