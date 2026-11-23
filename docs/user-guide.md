# Music Trainer: User Guide

Music Trainer is a browser-based practice tool for songs from YouTube. You can
slow a song down, repeat a passage, follow its beats, hear a metronome and
practice with individual instrument tracks.

## Getting started

If someone else runs the server for you, open the address they provide. To
install the application yourself, follow the
[Developer Guide](developer-guide.md#setup-and-running). Once installed,
start it as described below.

You can use the player as a guest or create an account. Search and new
downloads require an internet connection. First-time beat detection and
instrument separation also download model files.

> **Before starting a newly updated server:** the current version checks for
> unclaimed songs at startup and may delete them, including old downloads
> that were made before accounts were introduced. Back up the server's `data/`
> directory before upgrading or starting it if you want to keep those files.
> See [Data and backups](developer-guide.md#data-and-backups).

### Start the application

Open two terminals in the project directory. On Linux/macOS:

```bash
# Terminal 1
cd backend
.venv/bin/uvicorn music_trainer.app:create_app --factory --reload
```

```bash
# Terminal 2
cd frontend
npm run dev
```

On Windows PowerShell, use `.venv\Scripts\uvicorn` instead in terminal 1; the
other commands are the same. Open <http://localhost:5173> and leave both
terminals running. Press Ctrl+C in each to stop them. The second terminal
needs Node.js on its `PATH`. If the UI reports another port, open the address
shown by Vite.

Alternatively, after building the frontend, the backend can serve both parts
on port 8000; see [Single server](developer-guide.md#single-server).

## Find and open a song

1. Type a song name in the search box, or paste a YouTube video link.
2. Select a result to open it, or use **Add** to add it to your library. If
   the song is not already on the server, downloading starts automatically.
3. Open **Library** to see your songs and download progress. Use **Retry** if a
   download fails.
4. Open the song and press play. Beat detection and instrument separation may
   continue in the background after the download.

Library **Remove** removes the song and its presets from your library. The
server may also delete the shared song files if nobody else keeps the song;
see [Guest and account storage](#guest-and-account-storage).

## Player

### Playback and speed

Use the play/pause button, seek bar, volume control and fullscreen button as
you would in a video player. Speed ranges from 0.25× to 2× in 0.05× steps;
the application attempts to keep the original pitch as the speed changes.
The speed is displayed next to the controls. Independently changing the pitch
is not available in the current main version.

### Repeat a passage

1. Move to the beginning of the passage and select **Set A**.
2. Move to its end and select **Set B**. B must be after A.
3. Use **Loop On/Off** to enable or disable repetition. **Clear** removes the
   points.
4. Drag the handles on the timeline or use the arrows next to A and B for
   fine adjustments. With snapping off, the arrows move a point by 50 ms.

The gapless player uses an audio buffer to avoid a pause at the loop boundary.
If the browser or audio loading does not support this, the player falls back
to seeking the video, which can introduce an audible gap. For the original
video audio, loops longer than 15 minutes also fall back to seeking.

### Beats, bars and metronome

After detection, the timeline shows beat and bar markers. Under **Snap loop**:

- **Off** allows points between beats.
- **Beats** snaps points to beats.
- **Bars** snaps points to bar starts.

Snapping applies when setting or dragging loop points; the point arrows step by
one beat or bar when the corresponding mode is selected. Beat and bar
detection is an estimate, so check the markers against the music.

If the grid is wrong, use **½×** or **2×** to correct an incorrectly detected
tempo, choose the number of beats per bar, or use the **Bar start** arrows in
Bars mode to shift bar starts from the current position. **Steady** makes beats
evenly spaced for music played to a click. Reset buttons restore the detected
tempo or bar starts. Grid corrections are personal to your account, or to your
current browser when using the app as a guest.

Click **Metronome Off** to turn the click on once beats are available; the
button then shows **Metronome On**. **Click volume** is independent of the
song volume. Bar starts have a higher click. The metronome follows seeks, speed
and loops; it is off when a song opens and its volume is saved. The sound is
synthesized; custom drum samples are not currently supported.

### Zoom

Use **−** and **+** to zoom the timeline, **Fit loop** to show the selected
passage, and **Whole song** to return to the full timeline. Ctrl+scroll or a
pinch zooms around the pointer; Shift+scroll pans. The overview strip below a
zoomed timeline lets you drag its window or click another position.

### Instrument tracks and chords

When separation finishes, turn **Stems** on to hear the separated instruments
instead of the original mix. Each track has a waveform, volume slider,
**M** (mute) and **S** (solo); selecting a different solo replaces the previous
one. Turn stems off to return to the original mix and release their memory.
Click or drag on a track's timeline to seek.

Separation can take several minutes and the browser needs substantial memory
to load the tracks. The displayed progress or queue indicates what is
happening; use **Try again** if it fails. Separation is approximate and can
leave artifacts or instruments in the wrong track.

The chord lane shows estimated chords aligned with the beat grid. Corrections
to the grid can trigger a new chord analysis. Chord names are estimates, not a
guaranteed transcription.

### Save a practice preset

Presets store a practice setup for a song, including the loop or whole song,
snap mode, speed, stem mix and metronome.

1. Set the player up as desired and select **Save preset**.
2. Accept or edit the suggested name and select **Save**.
3. Select a preset to restore it. Double-click its name or use the edit
   button to rename it; use the delete button to remove it.
4. If you change a selected preset, **Changed** appears. Select **Update
   preset** to overwrite it, or **Save as new** to keep both versions.
   **Default** returns to the initial player setup.

Logged-in users can try presets made by people they follow and copy them using
**Add to my presets**.

### Keyboard shortcuts

The player also has a **Keyboard shortcuts** panel. Shortcuts do not run while
typing in a text field.

| Key          | Action                                         |
| ------------ | ---------------------------------------------- |
| Space / K    | Play or pause                                  |
| Left / Right | Seek backward or forward 5 seconds             |
| − / <, + / > | Decrease or increase speed by 0.05×            |
| A / B        | Set the loop start / end                       |
| L / C        | Toggle / clear the loop                        |
| G            | Cycle snapping: off, beats, bars               |
| S            | Save a preset                                  |
| 0 / 1–9      | Default / select one of the first nine presets |
| Z            | Toggle loop / whole-song zoom                  |
| Home         | Go to the loop start                           |
| M / F        | Mute / unmute; toggle fullscreen               |

When a loop handle has focus, its left/right arrow keys adjust that handle
instead of seeking.

## Accounts and community

Select **Register** to create an account, or **Log in** to use an existing
one. A username must be 3–30 letters, digits, dots, dashes or underscores;
the password must have at least eight characters. Songs, presets and settings
saved as a guest in the same browser are imported on login or registration.

Your profile shows practice history, starred songs and followers. On another
user's profile, select **Follow**; private profiles require approval. The bell
shows follow requests and other notifications. **Feed** shows activity; you
can also write comments under songs when logged in.

Use **Settings** for your profile description, profile privacy, password or
account deletion. A private profile shares its songs and practice history only
with accepted followers and is excluded from the everyone feed. Comments can
still be read under the song. Making the profile public accepts pending
requests. Deleting your account permanently removes its library and presets;
song files that no one else keeps may also be deleted.

## Guest and account storage

Guests' library entries, presets and player settings are stored in the
browser. Clearing site data, using another browser or blocking browser
storage can lose or hide them. Account data is stored on the server instead.
Downloaded song files and analysis are shared on the server.

A song is kept while an account has it. Otherwise, by default it is deleted
once no guest has opened or downloaded it for seven days. The server checks at
startup and hourly, and may also remove a song when an account removes it.
The retention period is configurable by the server operator.

## Troubleshooting

- **Nothing loads:** ensure both servers are running and open the frontend
  address (normally port 5173), not the backend API address. In the
  single-server setup, use the backend address instead (normally port 8000).
- **No sound:** check the player volume and mute, system output device and
  volume, and browser tab mute. Start playback with a click; browsers can block
  audio until a user interacts with the page.
- **Download fails:** check the internet connection, the video availability
  and server logs. The server needs `ffmpeg`; Deno is recommended for YouTube.
- **Beats or stems are not ready:** wait for the background job; use its retry
  control if it fails. Detection can be inaccurate, so adjust the beat grid.
- **Chords fail to load:** check the server logs. The backend's Python needs
  standard-library `lzma` support; see the developer guide's
  [troubleshooting section](developer-guide.md#deployment-and-troubleshooting).
- **Changes do not persist:** verify that browser site storage is enabled for
  guests, or that you are logged in to the intended account. Save errors
  shown in the player need to be resolved before relying on saved changes.

Use only material you are permitted to download and practice with; YouTube's
terms of service may restrict downloading.
