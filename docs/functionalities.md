### App for learning music from songs
web or desktop app for practicing music

Basic Functionality:
- get the audio (+ video) file from the internet (youtube) and store it locally
- set playback speed (relative and bmp - need to get bpm from the track)
- set practice loops (beat synchronized - need to get beats from the track)
- beat-synchronized metronome with a bar-start accent and separate volume
- separate tracks (drums, vocals, guitar, bass, ... - do not know how to do it yet / how reliably it can be done), mute / solo given tracks

Additional functionality:
- show notes / tabs for individual instruments (also needs to be extracted from the tracks or from another source of the song, maybe there is some database of midi files)
    - detect the key
    - detect chords and show them on a timeline
    - detect the tuning of the recording
    - import existing tabs / scores
    - align imported notation with the recording
- record the user attempts at the playing the parts and compare it to the track / notes
    - record, sync and compare by ear
    - automatic score (do not know if this is done / how)
- pitch shift / transpose (detuned recordings, Eb tuning, other key)
- auto-detect song sections (do not know if it is being done)
- progress and practice plan

---

### Work split (basic functionality, 3 people)

#### 1. Song import & track separation
Turn a YouTube link into a song folder the rest of the app can use.
- download audio + video from YouTube and store locally
- song library: list of stored songs (title, length, source URL)
- separate the audio into stems (drums, bass, vocals, guitar, piano, other), once per song, cached
- starting points: yt-dlp, Demucs (6-stem model)

#### 2. Beat & tempo analysis, loop logic
Find the beats and bars, so speed can be set in BPM and loops snap to the beat.
- detect BPM, beats and downbeats (first beat of each bar)
- speed in BPM: convert between target BPM and playback rate (rate = target BPM / song BPM)
- loop logic: snap loop start / end to the nearest beat or bar, move a loop by a beat or bar, save loops per song
- starting points: Beat This!, madmom, librosa

#### 3. Player & practice UI
Play the song for practice.
- playback: play / pause / seek, all stems and the video kept in sync
- speed change without changing pitch (in %, or in BPM using part 2)
- loop playback: seamless repeat between two points
- mixer: mute / solo / volume per stem
- UI: timeline with beat grid, loop selection, speed control, mixer
- starting points: Rubber Band or SoundTouch (time-stretching)

#### Shared song folder (agree on this first)
As implemented in `backend/src/music_trainer/services/library.py`:
```
data/library/<video-id>/
  meta.json       title, channel, duration, source URL, media file name   <- part 1 (done)
  video.mp4       downloaded video with audio                              <- part 1 (done)
  thumbnail.jpg                                                            <- part 1 (done)
  analysis.json   bpm, beats_per_bar, beats[], downbeats[], analyzer, hints <- part 2 (done)
  beat_activations.npz  beat network output (50 per second), to decode again  <- part 2 (done)
  loops.json      [{ id, name, start, end, snap_mode, playback_rate }]      <- part 3 UI (done)
  player.json     volume, muted, playback_rate, snap_mode, position, loop, active loop  <- part 3 UI (done)
  stems/          drums.wav, bass.wav, vocals.wav, ...                     <- part 1 (to do)
```
Example `analysis.json` (times in seconds; every downbeat is also a beat; `hints` are the user's fixes, see [beat-tracking.md](beat-tracking.md)):
```json
{ "bpm": 120.0, "beats_per_bar": 4, "beats": [0.51, 1.01, 1.51, 2.01, 2.51], "downbeats": [0.51, 2.51], "analyzer": "beat_this:final0+grid",
  "hints": { "beats_per_bar": null, "tempo_bpm": null, "bar_starts": [], "steady_tempo": false } }
```
Part 3 doesn't have to wait for parts 1 and 2: it can start with any audio file and a hand-written `analysis.json`.
