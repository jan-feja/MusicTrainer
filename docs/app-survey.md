### Survey of existing music practice apps
State as of October 2026. Built from vendor pages, app store listings and reviews. Several roundups are written by competing vendors (PracticeSession, StemConsole, Songscription), and prices / free-tier limits change often, so treat numbers as approximate.

---

#### TL;DR
- **No single app does the whole chain** (any song -> stems -> beat-synced loops + speed trainer -> notation -> feedback on your playing). Each category does one or two parts well.
- **Moises** is the closest to the audio side of our idea: stems (up to lead/rhythm guitar and individual drum parts), chords, key, BPM, beat/bar tracking, synced click, count-in, section detection, setlists, recording over the track.
- **PracticeSession** is the closest all-rounder (stems + speed trainer + MusicXML/Guitar Pro display + practice session manager, all desktop platforms). Worth a 14-day trial before building anything.
- **Feedback on your playing** (Yousician, Rocksmith+, Melodics, flowkey, Simply Piano) only works on each app's licensed song catalogue. No app found gives feedback on an arbitrary song you bring.
- **Notation synced to the real recording** exists (Songsterr, Soundslice, Guitar Pro 8), but the sync is made by people or from existing tabs, not generated from your audio.
- **AI transcription** (Klangio, Songscription, RipX) is a separate product category; drum transcription quality is disputed in reviews.
- **Speed trainer, gap/muted-bar training and practice logs** are common in notation apps, metronome apps and journal apps, but rarely combined with AI stems.

---

#### 1. Apps by category

##### A. Slow-downers / practice players (classic, mostly no AI)
| App | Platforms | Price (approx.) | Notable features |
|---|---|---|---|
| Transcribe! | Win, Mac, Linux | ~$39 one-time, 30-day trial | 1/20x to 2x speed, half-speed button, pitch in cents and up to 3 octaves, unlimited named loops, markers for sections/bars/beats with labels, spectrum with note & chord guessing, piano roll, EQ, karaoke/phase cancel, video, configurable shortcuts, foot pedals, batch export |
| Amazing Slow Downer | Win, Mac, iOS, Android | ~$40 desktop, ~$10-15 mobile | speed 20-200%, pitch +-12, A-B loops (10 per song), simple EQ, loop-count speed progression |
| Anytune | iOS, Mac, Android | ~$15-35 + add-ons | slow down, pitch, unlimited marks & loops, Step-It-Up speed trainer, FineTouch parametric EQ, ReFrame (frequency-focus isolation), Demix stems on Android (credits), LiveMix (play your instrument through the app), scrolling lyrics/text tabs, MIDI / Bluetooth remote control, count-in, folders & playlists, extract audio from video |
| AudioStretch | iOS, Android | ~$10, free Lite | near-frozen slowdown, waveform scrubbing to hear one note, pitch +-36, loops, spectrum keyboard, video |
| Transpose (browser ext.) | Chrome/Edge on YouTube etc. | free Classic, Pro sub | works directly on YouTube, speed 25-400%, pitch +-12/36, multiple markers & loop ranges, saved fragments with own settings; Pro: formant control, vocal reducer |
| Music Speed Changer / Up Tempo | Android (+iOS) | free + IAP | speed 15-500%, independent pitch/tempo, A-B loops, stem split on device (needs 4 GB RAM), formant correction (paid), export |

##### B. AI stem players with music analysis
| App | Platforms | Price (approx.) | Notable features |
|---|---|---|---|
| Moises | Web, desktop, iOS, Android, DAW plugin | Free tier; Premium $5.99/mo or $39.99/yr; Pro $29.99/mo | stems: vocals, drums, bass, guitar, piano, strings, other; Premium: lead/rhythm guitar, acoustic/electric, main/backing vocals; Pro: kick/snare/toms/hi-hat/cymbals; chord detection (beginner/intermediate/advanced), key, BPM, beat & bar tracking, smart metronome synced to song, count-in, AI section detection for loops, speed, pitch, capo mode, chords + lyrics view, AI lyrics (5 languages), setlists (collaborative), video recording over the track, export mixes/stems incl. click |
| PracticeSession | Win, Mac, Linux, iOS, Android | $39 desktop; mobile Pro $22.99 | speed 5-400%, pitch +-24, auto tuning detection (off A440), 8-band EQ, unlimited named regions & groups with per-region speed/pitch/EQ/volume, Speed Trainer, Key Acrobat (all 12 keys), custom sequences, AI stems (local or cloud) + mixer, MusicXML & Guitar Pro display with bar grid, LRC lyrics, Practice Manager (timed sessions, checklists, recap), setlists export, cloud sync |
| StemConsole | Web | Free; Pro $6.99/mo | 4 stems free / 6 stems Pro, live mixer, key & BPM, song-following click, tap tempo, "Hear my part" / "Play with the band", speed/key on stems, named loops, count-in; no chords, no YouTube import |
| Capo | Mac, iOS only | Free edition; ~$20-50/yr | chord detection (168 types + inversions, editable), key, beat detection (editable), section markers, chord diagrams for 5 instruments incl. left-handed & virtual capo, slow/loop/pitch, spectrogram tabbing view, MIDI & lead-sheet export (Mac), fully on-device, iCloud sync |
| Chordify | Web, iOS, Android | Free (daily limit) + Premium | chords from YouTube / SoundCloud / uploads (~36M songs), synced chord view, animated diagrams for guitar/uke/piano, transpose, capo, tempo, loops, MIDI/PDF export, tuner |
| Fender Songs | iOS (Apple Music) | $4.99/mo | chord detection on streamed songs, Practice / Play-along / Perform modes, scrolling chords & lyrics |
| Fadr | Web | free tier | stems + MIDI, chord, key & tempo detection (from a weak source) |

##### C. Tabs / notation synced with audio
| App | Platforms | Price | Notable features |
|---|---|---|---|
| Songsterr | Web, iOS, Android | Free + Plus | 400k songs / 1.3M tab tracks (guitar, bass, drums), auto-scrolling tabs with playback, community editing; Plus: original audio sync, speed, loop, print (sources differ on whether mute/solo, count-in, metronome and tuner are free or Plus) |
| Ultimate Guitar | Web, iOS, Android | Free + Pro tiers | huge tab/chord archive, "official" tabs, Pro: playback, speed, loop, smart auto-scroll adapting to speed, offline, Tonebridge effects |
| Guitar Pro 8 | Win, Mac (+ mobile app announced) | one-time | tab/score editor, audio track aligned with sync points, Speed Trainer (+% per loop), loops, visual & audio metronome, count-in, guitar/bass/drums/piano |
| Soundslice | Web | free basic + paid | notation/tab synced to YouTube or MP3 via sync points, click a note to jump, drag-to-loop snapping to notes/barlines, speed trainer, transpose, fretboard / keyboard (LH/RH) / violin / brass views, note names & rhythm counts above notes, synth overlay over real recording, multitrack stem mixer, metronome & count-in following tempo changes, focus mode (only loop bars shown), horizontal notation, video flip for left-handers, Notebook with practice history, MusicXML / Guitar Pro import, PDF/photo scanner, keyboard shortcuts |
| Tomplay / Metronaut | iOS, Android, web | subscription | classical-focused interactive sheet music with real backing tracks for many instruments; Metronaut (Antescofo) is known for accompaniment that follows your tempo (score following; not confirmed in the sources I checked) |

##### D. AI transcription (audio -> notes)
| App | Platforms | Notable features |
|---|---|---|
| Klangio (Guitar2Tabs, Piano2Notes, Drum2Notes, Sing2Notes, Scan2Notes, Transcription Studio) | Web, iOS, Android, DAW plugin | per-instrument models; export to PDF, MIDI, MusicXML, Guitar Pro; edit mode; songbook; from ~GBP 4/mo. Reviews say drum transcription still needs manual fixing (feel, ghost notes) |
| Songscription | Web | audio / MIDI / YouTube link -> sheet music & tabs, 10+ instruments, built-in editor & piano roll, tabs only in standard tuning |
| RipX DAW | Win, Mac | stem separation + audio-to-MIDI + note-level editing of audio, $99-198 |
| Capo (Mac), Transcribe! | desktop | semi-automatic: spectrogram / note guessing, the human decides |

##### E. Learn-with-feedback apps (gamified, own catalogue)
| App | Instruments | Notable features |
|---|---|---|
| Yousician | guitar, bass, piano, ukulele, voice | mic-based real-time scoring of pitch & timing, 10k+ songs & lessons, structured paths, weekly missions, artist courses |
| Rocksmith+ | guitar, bass, piano | plug-in cable or mic (piano via MIDI or mic), note highway, Riff Repeater (loop a section, change speed and note density), Note-by-Note (waits for the right note), Adaptive Difficulty (adds/removes notes by accuracy) |
| Melodics | keys, pads, e-drums, acoustic drums | hit / miss / early / late display, Practice mode (loop + slow down), Wait mode, Auto BPM, Playground, guided paths, streaks, trophies, daily goal |
| flowkey | piano | Wait mode via mic or MIDI, loop, slow motion (50/75%), hands separately |
| Simply Piano | piano | mic recognition (MIDI more accurate), 5k+ songs, 5-minute daily workouts |
| Synthesia | piano (MIDI) | falling notes, any MIDI file, hands separately, slow down, melody practice waits for you |
| JustinGuitar, Fender Play, Drumeo | guitar / drums | video lessons + song players with tempo control, chord prompts; Drumeo: play-alongs sorted by tempo/level/style, 5000+ songs with removable drums |

##### F. Practice support tools
| Area | Apps | Notable features |
|---|---|---|
| Metronomes / timing | Time Trainer (JustinGuitar), Metronome & Rudiment Practice, Time Guru, GhostClick | gap click (play 3 bars, mute 1), random beat drop / random muted bars, speed-upper per N bars, timed tempo programs, setlists |
| Backing tracks | iReal Pro, Jamzone, Karaoke Version, Drumeo | iReal: backing band from chord charts, 50 styles, tempo +1..20 BPM each chorus, auto transposition each chorus, loop >= 2 bars; Jamzone: 70k real studio multitracks, mute/solo per instrument, tempo & key, chords, synced lyrics, setlist sharing, offline |
| Practice journals | Modacity, Andante, Instrumentive | practice lists, "deliberate practice" button, tempo history, timer, recorder, drone tuner, streaks, mood/focus tracking, goals, calendar, reminders, log export |
| Sheet readers | forScore | page turns by Bluetooth pedal (AirTurn, PageFlip), face gestures (mouth / wink / head turn), AirPods head gestures |
| Ear training | EarMaster, Functional Ear Trainer, ToneGym | intervals, chords, functional hearing in a key context, sing/clap answers, rhythm training |

##### G. Free / open-source
| Project | What it does |
|---|---|
| Demucs | the stem separation model most free tools are built on (4 stems, or 6 incl. guitar & piano) |
| StemRoller, StemDeck, MISST | desktop GUIs around Demucs; StemRoller has YouTube search, StemDeck runs the 6-stem model locally for practice |
| drumsep | community Demucs model splitting drums into kick, snare, toms, cymbals |
| Audacity | free editor, slow-down only as a destructive edit, no saved loops |

No open-source all-in-one practice app (stems + loops + trainer + notation) showed up in the search.

---

#### 2. Feature catalogue (everything found, grouped)

**Getting songs in**
- Local files (mp3, wav, flac, m4a, aiff), audio CDs - most desktop apps; Transcribe! reads CDs
- Audio from video files - Anytune
- Cloud import (Google Drive, Dropbox, iCloud, public URLs) - Moises, Anytune
- YouTube directly - Transpose (in browser), Soundslice, Chordify, Songscription, StemRoller
- Streaming services - Anytune Android (tempo of Spotify / Apple Music), Fender Songs (Apple Music); Capo explicitly can't
- Licensed catalogues - Songsterr, Yousician, Jamzone, Drumeo, Chordify

**Playback & audio**
- Pitch-preserving speed (ranges from 5% to 500%), one-tap half speed - all slow-downers
- Pitch shift in semitones and cents, up to +-3 octaves - Transcribe!, AudioStretch, Transpose
- Automatic detection of recordings tuned off A440 - PracticeSession
- Formant control - Transpose Pro, Music Speed Changer
- Parametric / multi-band EQ, frequency-focus isolation - Transcribe!, Anytune ReFrame, PracticeSession
- Karaoke / phase cancel, vocal reducer - Transcribe!, Transpose Pro
- Spectrum / spectrogram, note scrubbing - Transcribe!, Capo, AudioStretch
- Video in sync, mirrored video for left-handers - Transcribe!, Soundslice
- Export modified audio, batch export - Transcribe!, Capo, Moises

**Loops, markers, structure**
- Unlimited named loops; loop groups; per-loop speed/pitch/EQ/volume - Transcribe!, Anytune, PracticeSession
- Drag-to-loop snapping to notes / barlines / beats - Soundslice, Capo
- Markers for sections, bars and beats with labels and colours - Transcribe!, Capo, Anytune
- AI section detection - Moises
- Loop sequences - PracticeSession
- Focus mode (hide everything outside the loop) - Soundslice
- Count-in - Moises, Anytune, Songsterr, Guitar Pro, Soundslice, StemConsole

**Trainers**
- Speed trainer (+% or +BPM per repeat) - Anytune, Guitar Pro 8, Soundslice, PracticeSession, iReal Pro, Amazing Slow Downer, Time Trainer
- All-12-keys trainer / auto-transpose each repeat - PracticeSession, iReal Pro
- Gap click, random muted bars, random beat drop - Time Trainer, Time Guru, GhostClick
- Adaptive difficulty (fewer / more notes) - Rocksmith+
- Wait mode / note-by-note - flowkey, Melodics, Synthesia, Rocksmith+

**Analysis**
- BPM & key - Moises, StemConsole, Fadr, Capo
- Beat & bar tracking, editable beat grid, tap tempo - Moises, Capo (editable), StemConsole
- Chord detection with difficulty levels, capo suggestions, inversions - Moises, Capo, Chordify, Fender Songs
- Note / chord guessing on a spectrum, piano roll - Transcribe!
- AI lyrics transcription - Moises

**Stems**
- 4 stems (vocals, drums, bass, other) - nearly all AI apps, often free
- 6+ stems (guitar, piano, strings) - Moises, StemConsole Pro, StemDeck
- Lead vs rhythm guitar, acoustic vs electric, main vs backing vocals - Moises Premium
- Drum parts (kick, snare, toms, hi-hat, cymbals) - Moises Pro, drumsep
- Mixer (mute / solo / volume), "minus one", "hear my part" - all stem apps
- Speed & key change on separated stems - StemConsole Pro
- On-device vs cloud processing - Capo & StemDeck local, PracticeSession both, Moises cloud
- Real multitracks instead of AI - Jamzone, Karaoke Version, Drumeo drumless

**Notation & transcription**
- Tabs synced to the original recording - Songsterr, Soundslice, Guitar Pro 8
- Instrument views (fretboard, keyboard with LH/RH, violin, brass), note names, rhythm counts - Soundslice
- Chord diagrams for guitar/bass/uke/banjo/mandolin, left-handed - Capo
- Chord chart view, chords + lyrics view, lyrics-only view - Soundslice, Moises
- Import MusicXML, Guitar Pro, MIDI; scan PDF / photo - Soundslice, PracticeSession, Synthesia, Klangio
- Synth overlay on top of the real recording - Soundslice
- AI transcription to tab / sheet / MIDI / MusicXML / GP - Klangio, Songscription, RipX, Fadr, Capo (Mac)
- Notation editor, community tab editing - Soundslice, Guitar Pro, Songsterr

**Feedback & recording**
- Real-time pitch & timing scoring through mic - Yousician, Simply Piano, flowkey, Melodics (acoustic drums), Rocksmith+
- MIDI input for keys / e-drums - Synthesia, flowkey, Melodics, Rocksmith+ piano
- Hit / miss / early / late display, accuracy scores - Melodics
- Record video + audio over the track and share - Moises
- Play your instrument through the app mixed with the track - Anytune LiveMix, UG Tonebridge effects
- Accompaniment that follows your tempo - Metronaut (score following)

**Hands-free & UI**
- Configurable keyboard shortcuts - Transcribe!, Soundslice
- Foot pedals, MIDI controller, Bluetooth keyboard - Transcribe!, Anytune, forScore
- Face gestures, AirPods head gestures - forScore Pro
- Fullscreen, layout options, horizontal single-line notation, smart auto-scroll - Soundslice, Ultimate Guitar

**Organisation, progress, sharing**
- Folders, playlists, setlists (collaborative, export to PDF) - Anytune, Moises, PracticeSession, Jamzone
- Cloud sync across devices - Capo, PracticeSession, Jamzone
- Practice session runner (timed blocks, checklist, recap) - PracticeSession
- Practice journal (time, tempo history, notes, mood / focus, goals, calendar, streaks) - Andante, Modacity, Instrumentive, Soundslice Notebook
- Gamification (paths, missions, trophies, daily goals) - Yousician, Melodics
- Share loops / marks / setups via link or email - Anytune, Soundslice, StemConsole
- Offline use - Capo, Jamzone

**Other**
- Tuner, drone tuner - Songsterr, Chordify, Andante
- Backing band generated from chord charts - iReal Pro
- Ear training (intervals, functional, sing / clap answers) - EarMaster, Functional Ear Trainer, ToneGym, Anytune interval trainer

---

#### 3. Comparison of key apps
Legend: ✓ yes, ~ partial / limited, - no, ? not confirmed in the sources checked.

| Feature | Transcribe! | Anytune | Moises | Capo | PracticeSession | Songsterr | Soundslice | Rocksmith+ |
|---|---|---|---|---|---|---|---|---|
| Platforms | Win/Mac/Linux | iOS/Mac/Android | Web/desktop/mobile | Mac/iOS | all desktop + mobile | Web/mobile | Web | PC/console/mobile |
| Pricing | one-time | one-time + add-ons | subscription | subscription | one-time | subscription | freemium | subscription |
| Slow down, keep pitch | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (Plus) | ✓ | ✓ |
| Pitch shift | ✓ | ✓ | ✓ | ✓ | ✓ | ? | ✓ | ? |
| Saved named loops | ✓ | ✓ | ✓ | ✓ (paid) | ✓ | ✓ (Plus) | ✓ | ✓ |
| Automatic speed trainer | - | ✓ | ? | - | ✓ | ? | ✓ | ✓ |
| Beat / bar grid | ~ manual | ? | ✓ auto | ✓ auto + edit | ~ from notation | ✓ from tab | ~ manual sync | ✓ |
| Click / count-in on song | ? | ~ count-in | ✓ | ? | ? | ✓ | ✓ | ? |
| AI stems | - | ~ Android only | ✓ | - | ✓ | - | ~ uploaded stems | - |
| Chord detection | ~ guessing | - | ✓ | ✓ | - | from tab | from notation | - |
| Notation / tab synced | - | ~ text tabs | ~ chords | ~ export (Mac) | ✓ | ✓ | ✓ | ✓ |
| Feedback on your playing | - | - | - | - | - | - | - | ✓ |
| Record yourself | ~ input only | ~ LiveMix | ✓ | - | ? | - | ? | - |
| Hands-free control | ✓ | ✓ | ? | ? | ? | ? | ✓ | ? |
| Practice log | - | - | ? | - | ✓ | - | ✓ | ? |

---

#### 4. Ideas found here that are not in README.md yet
Same effort tags as in the README.

- [ ] Per-loop settings: each loop remembers its own speed, pitch, EQ and mix `E`
- [ ] Focus mode: show only the looped bars `E`
- [ ] Key trainer: loop goes through all 12 keys / transposes each repeat `E`
- [ ] Random muted bars / random beat drop (variant of gap training) `E`
- [ ] Simplified chords: beginner / intermediate / advanced chord level `M`
- [ ] Capo suggestion with easier chord shapes `M`
- [ ] Left-handed mode: mirrored video, left-handed fretboard and chord diagrams `E`
- [ ] Note names and rhythm counts shown above notation `M`
- [ ] Wait mode: playback waits until you play the right note (MIDI first, mic later) `M`
- [ ] Adaptive difficulty: show fewer notes first, add more as accuracy improves `H`
- [ ] Play your instrument through the app, mixed with the track (+ amp / effect presets) `M`
- [ ] Accompaniment follows your tempo (score following) `H`
- [ ] Backing band generated from a chord chart (iReal Pro style) `H`
- [ ] AI lyrics transcription `M`
- [ ] Scan sheet music (PDF / photo -> notation) `H`
- [ ] Face / head gestures for hands-free control `H`
- [ ] Drone note for intonation practice `E`
- [ ] Practice session runner: timed blocks, checklist, end-of-session recap `E`
- [ ] Journal fields: mood / focus, goals, calendar `E`
- [ ] Batch export (e.g. all loops at several speeds) `E`

Notes on existing README items:
- Some items tagged `H` in the README exist commercially: lead vs rhythm guitar split and drum-part split (Moises), section detection (Moises), drum transcription (Klangio Drum2Notes, accuracy disputed). They still rely on proprietary models, so the `H` tags stay for building it ourselves; drum-part split has an open model (drumsep).
- "Metronome click on the detected beats" and "count-in" are standard in Moises, Soundslice and StemConsole.

---

#### 5. Where our app could stand out
- **One place for the whole chain**: today people combine Moises (stems), Songsterr / Soundslice (tabs), a metronome app (gap training) and a journal app (log).
- **Practice tools on top of stems**: speed trainer, gap training, key trainer, per-loop settings are common in classic or notation apps but rarely described in AI stem apps.
- **Fixable analysis**: Capo is the only app found that clearly lets you edit detected beats and chords (StemConsole allows manual BPM / tap tempo); the others don't describe a way to correct results.
- **Feedback on any song**, not only a licensed catalogue (hard; MIDI input for keys / e-drums is the realistic start).
- **Local and free**: Capo and StemDeck show stems/analysis can run on-device; most competitors are subscriptions with free-tier limits (e.g. 5 songs a month).

---

#### Sources
Official pages
- Soundslice features: https://www.soundslice.com/features/
- Transcribe!: https://www.seventhstring.com/xscribe/overview.html
- Capo: https://supermegaultragroovy.com/products/capo/
- Anytune: https://www.anytune.app/
- Moises features: https://moises.ai/features/
- Moises App Store listing: https://apps.apple.com/app/id1515796612
- Moises separable instruments: https://help.moises.ai/hc/en-us/articles/360010972019-Which-instruments-can-be-separated-on-the-Moises-Pro-plan
- Songsterr: https://www.songsterr.com/about
- Guitar Pro 8 speed: https://www.guitar-pro.com/docs/gp8/audio/playback/speed
- Guitar Pro 8 what's new: https://www.guitar-pro.com/docs/gp8/basics/intro/whats-new
- Ultimate Guitar Pro: https://help.ultimate-guitar.com/en/articles/6741560-what-do-i-get-if-i-subscribe-to-pro
- iReal Pro practicing: https://irealpro.com/dwkb/practicing/
- Transpose FAQ: https://transpose.video/faq/
- forScore face gestures: https://forscore.co/face-gestures/
- Melodics: https://melodics.com/info/ai-info-page
- Yousician: https://yousician.com/about
- Jamzone: https://www.jamzone.com/singer.html
- EarMaster: https://earmaster.com
- Drum2Notes (Klangio): https://apps.apple.com/app/id6717586517
- Metronaut: https://apps.apple.com/us/app/metronaut-sheet-music/id1202148484
- Time Trainer Metronome: https://apps.apple.com/app/id502491350
- Andante: https://apps.apple.com/us/app/-/id1530262372
- Modacity: https://apps.apple.com/us/app/-/id1351617981
- Functional Ear Trainer: https://apps.apple.com/app/id1088761926
- StemRoller: https://github.com/stemrollerapp/stemroller
- drumsep: https://huggingface.co/vincewin/drumsep

Comparisons and reviews (some by competing vendors)
- PracticeSession vs Amazing Slow Downer vs Anytune: https://www.practicesession.app/blog/practice-session-vs-amazing-slow-downer-vs-anytune/
- Songscription, slow-down apps: https://www.songscription.ai/blog/best-apps-to-slow-down-music
- StemConsole, learning songs by ear: https://stemconsole.ai/blog/best-apps-to-learn-songs-by-ear/
- Songsterr review (Guitar Coach): https://guitarcoachmag.com/reviews/expanding-the-world-of-tabs/
- Chordify review: https://www.guitarchalk.com/chordify-review/
- Rocksmith+ accessibility (Ubisoft): https://news.ubisoft.com/en-us/article/5XfINjoRmVJgBKR8fGt4EM/rocksmith-accessibility-spotlight
- flowkey: https://pianistmagazine.com/blogs/learn-all-the-songs-that-you-love-with-flowkey
- Synthesia review: https://pianoers.com/synthesia-piano-review/
- Simply Piano review: https://pianoers.com/simply-piano/
- Klangio Transcription Studio: https://www.soundonsound.com/news/klangio-launch-transcription-studio
- Songscription launch: https://techcrunch.com/2025/06/30/songscription-launches-an-ai-powered-shazam-for-sheet-music
- RipX DAW: https://www.musicradar.com/news/ripx-ai-daw
- Drumeo drumless tracks: https://drummingnewsnetwork.com/?p=12256
- Fender Songs: https://guitar.com/news/industry-news/fender-songs-launch/
- Practice journal apps: https://www.ensembleschools.com/blog/apps-for-musicians/
- StemDeck: https://community.justinguitar.com/t/stemdeck-a-free-moises-alternative/414339
- Music Speed Changer: https://www.apkmirror.com/apk/single-minded-productions-llc/music-speed-changer
