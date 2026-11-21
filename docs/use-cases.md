### App for learning music from songs
web or desktop app for practicing music

Basic Functionality:
- get the audio (+ video) file from the internet (youtube) and store it locally
- set playback speed (relative and bmp - need to get bpm from the track)
- set practice loops (beat synchronized - need to get beats from the track)
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

### Use case ideas (brainstorm)
A raw list to cut down later: tick `[x]` or delete lines.
Rough effort guess: `E` easy (UI work or a ready-made library), `M` medium, `H` hard / unreliable with today's tech.

#### Songs & library
- [ ] Import a local audio file (mp3, wav, flac, m4a) `E`
- [ ] Download from sites other than YouTube (SoundCloud, Bandcamp, ...) `E`
- [ ] Search YouTube from inside the app `M`
- [ ] Keep the video and play it in sync (watch the player's hands) `M`
- [ ] Song library with search, tags and status (learning / learned) `E`
- [ ] Auto-fill title, artist, cover art `M`
- [ ] Remember everything per song: loops, speed, markers, stem mix, last position `E`
- [ ] Notes per song (fingerings, tips, links to lessons) `E`
- [ ] Setlists / playlists `E`
- [ ] Back up and restore the library `E`

#### Playback
- [ ] Waveform view with zoom, play / pause / seek `E`
- [ ] Pitch shift / transpose in semitones and cents (detuned recordings, Eb tuning, other key) `E`
- [ ] "Jump back 1 / 2 bars" button `M`
- [ ] EQ / band filter to bring out one frequency range `E`
- [ ] Play only the left / right channel, or remove the centre (old stereo mixes, quick karaoke) `E`
- [ ] Spectrogram view for finding notes by ear `E`

#### Loops & song structure
- [ ] Named, saved loops; nudge start / end by a beat or a bar `E`
- [ ] Set a loop by bar numbers (bars 17-24) `M`
- [ ] Section markers (verse, chorus, solo) set by hand `E`
- [ ] Auto-detect song sections `H`
- [ ] Count-in before each repeat `E`
- [ ] Pause of N beats between repeats `E`
- [ ] Speed trainer: start slow, speed up every N repeats until a target speed `E`
- [ ] Loop chain: loop A x4, then loop B x4, ... `M`
- [ ] Gap training: the track goes silent for a few bars and comes back, to check you kept time `M`

#### Beat, tempo & harmony analysis
- [ ] Metronome click on the detected beats, accented downbeat `M`
- [ ] Fix the beat grid by hand: tap tempo, move the downbeat, set time signature `M`
- [ ] Tempo map for songs that speed up / slow down (live recordings) `H`
- [ ] Detect the key `M`
- [ ] Detect chords and show them on a timeline `M`
- [ ] Detect the tuning of the recording (e.g. A = 432 Hz, half step down) `M`

#### Stems
- [ ] Mute / solo / volume per stem `E`
- [ ] One-click "minus me": mute my instrument, play the rest `E`
- [ ] Compute stems once per song and cache them `E`
- [ ] Separation runs in the background with progress; choose speed vs quality `M`
- [ ] Export stems, or a loop with the current mix and speed, as an audio file (practice on phone) `M`

#### Notation & transcription (all instruments)
- [ ] Transcribe a stem to MIDI `M`
- [ ] Import existing tabs / scores (Guitar Pro, MusicXML, MIDI, text tabs) `M`
- [ ] Align imported notation with the recording `H`
- [ ] Notation / tab scrolls with playback, cursor follows the music `M`
- [ ] Piano-roll view of the notes `M`
- [ ] Correct a transcription by hand `H`
- [ ] Play the transcription as a synth sound next to the original `M`
- [ ] Export a transcription (MIDI, MusicXML, Guitar Pro) `M`

#### Guitar
- [ ] Tuner (microphone or audio interface) `E`
- [ ] Alternate tunings and capo, reflected in tabs `M`
- [ ] Chord diagrams for detected chords `M`
- [ ] Fretboard view showing the notes being played `M`
- [ ] Split lead vs rhythm guitar `H`
- [ ] Strumming pattern display `H`

#### Bass
- [ ] Bass line to tab (single-note lines transcribe well) `M`
- [ ] Shift the bass an octave up so it's audible on small speakers `E`
- [ ] "Kick + bass only" mode for locking in with the drums `E`
- [ ] Show chord roots / how the bass note relates to the chord `M`

#### Drums
- [ ] Drum stem to drum notation / drum tab `H`
- [ ] Split the drum stem into kick, snare, hi-hat, cymbals `H`
- [ ] Electronic kit as MIDI input for timing comparison `M`
- [ ] Highlight fills `H`

#### Keys / piano
- [ ] Falling-notes view over a keyboard (Synthesia style) `M`
- [ ] MIDI keyboard input (far more accurate than a microphone) `M`
- [ ] Chord voicings shown on a keyboard `M`
- [ ] Split left / right hand `H`

#### Vocals (just in case)
- [ ] Pitch curve of the vocal stem vs your own voice `M`
- [ ] Synced lyrics `M`

#### Recording & feedback
- [ ] Record yourself over the track (mic, audio interface or MIDI) `M`
- [ ] Latency calibration `M`
- [ ] Play back your take mixed with the original `E`
- [ ] Keep takes, mark the best one `E`
- [ ] Timing feedback: early / late against the beat grid `M`
- [ ] Note accuracy against the transcription `H`
- [ ] Webcam video of yourself to check technique `M`

#### Hands-free control
- [ ] Keyboard shortcuts for everything `E`
- [ ] Foot pedal (Bluetooth page-turner or MIDI foot controller) `E`
- [ ] Large "practice mode" UI readable from a distance `E`
- [ ] Voice commands ("again", "slower") `H`

#### Progress & planning
- [ ] Practice timer and log per song / section `E`
- [ ] Track the highest clean speed per loop over time `E`
- [ ] Status per section: learning / OK / mastered `E`
- [ ] Daily practice plan, spaced repetition of sections `M`
- [ ] Streaks, reminders `E`

#### Ear training
- [ ] Hide the notation until you've tried by ear `E`
- [ ] "What note is this?": show the pitch at the cursor `M`
- [ ] Chord quiz using the song's own chords `M`

#### Other
- [ ] Works offline once a song is processed `E`
- [ ] Share a song setup (loops, markers) with a friend / teacher `M`
- [ ] Phone / tablet version, or sync between devices `H`
