# Beat tracking: method and measurements

How the app finds beats and bars, how that was tested, and what is still hard. Code: `backend/src/music_trainer/services/beat_decoding.py`; experiments: [../experiments/test_beat_tracking.py](../experiments/test_beat_tracking.py).

## The problem

The first version took the beats and bar starts straight from the [Beat This!](https://github.com/CPJKU/beat_this) network (peak picking). On Joe Satriani's *Cryin'*, which is steady at 75.5 BPM in 4/4, 20 % of the bars came out wrong:

- **1:29–1:57:** the network also saw bar starts in the middle of bars, so the grid had half bars.
- **4:27–4:56:** it counted eighth notes as beats.

Peak picking lets every bar have its own length, and in real music they almost never do.

## Is there a better model?

Not one that can be used:

- **Beat This!** (ISMIR 2024) is still the best open model with published weights.
- **Newer research models:** BeatFM and AlignBeat (2025), "Explore This!" and the masked-diffusion tracker (2026) report gains of a few points. None has released code and weights.

The fix is in the step after the network. Beat This! deliberately leaves out musical assumptions. madmom's "DBN" adds them back, but it has two drawbacks:

- it allows only 3 or 4 beats per bar;
- it is unmaintained, and installing it needs a C compiler.

## The decoder

The app keeps the network's output (how likely a beat and a bar start are, 50 times per second) and finds the most likely beat grid under a few assumptions. It is a bar-pointer model (Krebs et al. 2015) written in numpy:

1. **Steady tempo:** the tempo changes only gradually from beat to beat.
2. **One meter per section:** within a section every bar has the same number of beats, 3 to 8. The meter may change between sections of at least 4 bars (a verse in 3/4, a chorus in 4/4); see [Meter and tempo changes](#meter-and-tempo-changes). 2 is available only as a user hint.
3. **No jumps to double or half tempo:** if the best grid spans about a factor of 2 (75 and 150 BPM), the song is decoded once per tempo octave and the likelier one is kept. Smaller spreads (76 → 140 BPM) are real tempo changes and are followed.
4. **Click tracks:** if the network rates bar starts no higher than any other beat (e.g. a click track), there is no meter to find, so the grid gets 4 beats per bar.
5. **Precise timing:** beat times are refined to well below the network's 20 ms frames (parabolic peak, local straight-line fit).

The network output is stored with the video. The user's fixes (**hints**) therefore only decode again: a few seconds, or instantly for bar starts. The hints are:

- **½× / 2×:** the tempo octave (75 vs 150 BPM).
- **Beats per bar:** set one meter for the whole song (no sections). *Auto* shows what was detected, e.g. *Auto (4, 3)*.
- **‹ Bar start ›:** move the bar starts one beat from the playhead on, to the end of that section. This fixes the bars after a real odd bar and leaves the bars before it, and the next sections, alone.
- **Steady:** space all beats exactly evenly, so every bar has the same length (for songs played to a click).

**Tried and dropped** (numbers in the experiment results):

- **Single bars of another length:** the first try (an odd bar allowed anywhere, at a cost) invented odd bars (15–37 % in some songs). With the regression set ([Meter and tempo changes](#meter-and-tempo-changes)) a better version gets the meter songs further than sections alone, but it still breaks songs that were right. Meter changes are now allowed between sections instead.
- **2 beats per bar as an automatic choice:** turned 13 % of real 4/4 songs into half bars.
- **A steadier tempo prior (λ = 200–400):** helped some songs, hurt others.
- **Averaging three network checkpoints:** small gains for three times the computing time.
- **Fitting a constant tempo automatically:** gained only 0.4 ms. It is offered as the *Steady* hint instead.

## Test data

| Set | What | Answers |
|---|---|---|
| **Score songs** (51) | 17 songs written as scores ([make_score_songs.py](../experiments/make_score_songs.py)), each at 3 tempi, rendered with FluidSynth, effects and human timing jitter ([score_to_audio.py](../experiments/score_to_audio.py)). Categories: steady rock, ballad with half- and double-time sections, metal, 3/4, 6/8, 12/8, 5/4, 7/4, single 2/4, 3/4 and 6/4 bars in a 4/4 song, tempo jumps and ritardando, rubato intro, drifting live tempo, no drums, swing, funk, reggae one-drop, stops | exact, from the score |
| **GTZAN** (991 clips of 30 s) | real recordings, 10 genres; **not** in Beat This!'s training data | human annotations ([CPJKU/beat_this_annotations](https://github.com/CPJKU/beat_this_annotations)) |
| **Harmonix** (8 songs) | real songs, downloaded from YouTube | human annotations; Beat This! was trained on them, so the network side is optimistic |
| **Library** | songs downloaded in the app (*Cryin'*, *Charlie*) | none; checks that need no answers (bar regularity) |
| **Score songs with changes** (33) | 11 more score songs at 3 tempi (`make_score_songs.py --set changes`): verses in 3/4, 5/4, 6/4, 7/4 or 7/8 against a 4/4 chorus, a waltz verse with a rock chorus at another tempo, a 4+4+4+3 bar cycle, a verse like Tool's *Pneuma* (6+6+5+6+5+5 eighths), tempo jumps with an accelerando and a ritardando, a rubato ballad, an accelerating waltz | exact, from the score |
| **Harmonix with changes** (31 songs) | Harmonix songs whose annotations change meter (22: Soundgarden *The Day I Tried to Live*, Killswitch Engage *My Curse*, Metallica *Blackened*, Rush *Tom Sawyer* and *The Camera Eye*, Megadeth *Five Magics*, ...) or tempo (9: *Baba O'Riley*, *Good Mourning / Black Friday*, ...), chosen from the annotations ([get_harmonix_changes.py](../experiments/get_harmonix_changes.py)) | human annotations, moved onto the YouTube audio by DTW against the mel spectrograms the Harmonix authors publish (most YouTube versions are other edits); 11 of the 42 downloaded songs did not line up and were left out |
| **Regression set** (226) | network outputs and answers of the score songs, both Harmonix sets, 100 GTZAN clips and 3 library songs, stored in the backend ([backend/tests/data/beat_grids](../backend/tests/data/beat_grids/README.md)) | as above |

`score_to_audio.py` also renders Guitar Pro 3/4/5 tabs and any MIDI file. Repeats, alternate endings, tempo changes and time signatures are played out. Any tab becomes a test song with exact beats and bars.

**Metrics** (70 ms tolerance):

- **Loop test:** set A on a true bar start, step 1 / 4 bars in the detected grid, and check whether B is the right bar start. An extra or a missing bar start makes it fail, which plain snapping would not show.
- **F-measure:** of beats and of bar starts.
- **Continuity:** the share of the song tracked at the right tempo and phase. It drops when a tracker switches tempo octave or shifts the bars.

## Results

GTZAN (real, held out):

| Method | Beats F | Bar starts F | Bar continuity | 1-bar loop | 2-bar loop | Meter right | Odd bars |
|---|---|---|---|---|---|---|---|
| Peak picking (first version) | 0.894 | 0.788 | 0.679 | 0.666 | 0.653 | 0.78 | 14 % |
| madmom DBN (3 or 4) | 0.882 | 0.777 | 0.735 | 0.695 | 0.691 | 0.95 | 0 % |
| **App decoder** | 0.884 | 0.780 | 0.735 | 0.696 | 0.692 | 0.94 | 0 % |
| App decoder, 3 checkpoints averaged | 0.892 | 0.790 | 0.749 | 0.713 | 0.709 | 0.95 | 0 % |

Score songs (exact answers):

| Method | Bar starts F | Bar continuity | 1-bar loop | 4-bar loop | Beat timing spread | Odd bars |
|---|---|---|---|---|---|---|
| Peak picking | 0.794 | 0.602 | 0.631 | 0.575 | 4.7 ms | 17 % |
| madmom DBN | 0.745 | 0.622 | 0.627 | 0.615 | 5.0 ms | 0 % |
| **App decoder** | 0.863 | 0.784 | 0.784 | 0.775 | 2.6 ms | 0 % |
| App decoder, 3 checkpoints averaged | 0.866 | 0.795 | 0.796 | 0.786 | 2.5 ms | 0 % |

Harmonix: 4-bar loops 0.827 (peak picking), 0.751 (madmom), 0.853 (app); bar continuity 0.859 / 0.787 / 0.894.

*Cryin'*: all 103 bars have 4 beats (before: 20 % odd bars). Bars are 3.16–3.23 s long, or exactly 3.179 s with *Steady*.

**By category** (score songs; bar starts F of the app decoder, each song at 3 tempi):

- **Fully right (1.00):**
  - steady rock, funk, no drums, stops;
  - 3/4, 5/4 and 7/4 (peak picking: 0.53 on 5/4 and 7/4, with no 4-bar loop right at all);
  - 6/8 folk.
- **Nearly right:**
  - **Tempo jumps, ritardando, rubato intro, drifting live tempo:** 0.98.
  - **Single 2/4, 3/4 and 6/4 bars in a 4/4 song:** 0.92. The bars right after an odd bar can be shifted until the user moves the bar starts there.
- **Wrong in a way the user fixes with one hint:**
  - **Swing:** the beats are always right. At 2 of the 3 tempi the bar starts land on beat 3, so ‹ Bar start › fixes it. madmom fails the same way.
  - **Reggae one-drop:** the network takes the drop on beat 3 for the bar start, at double tempo. Use ½× and ‹ Bar start ›.
  - **Metal at 180 BPM:** heard as 90 BPM, which many listeners would also tap. Use 2×.
  - **12/8 shuffle:** bars come out half as long. Set the beats per bar.
  - **Ballad with a double-time section:** it keeps one tempo, but with 2 beats per bar. Set 4 beats per bar.

  These are genuine ambiguities. Every decoder tested got them wrong, and the hints fix each in one or two clicks.

## Meter and tempo changes

The first decoder assumed one meter and one tempo octave per song. That holds for most songs, but not for songs like Tool's *Pneuma* (4/4 parts, verses in 6/8 and 5/8 bars) or songs that speed up. To measure this before changing anything, the test sets above got songs whose meter or tempo changes, and the backend got a **regression test** (`pytest -m beat_regression -s`, ~40 s). It decodes 226 songs from their stored network output and compares the bars with the true ones and with a stored baseline:

- every group (steady, tempo changes, meter changes) must keep its mean beat and bar-start F-measure and loop accuracy;
- every song whose bar starts were right (F ≥ 0.9) must stay right;
- the library songs must keep their meter and tempo (*Cryin'* also must not get a double-time stretch again).

### What changed

1. **Meter sections.** After the beats are decoded, a second pass labels them with bars again (`_meter_sections`). Within a section every bar has the same number of beats (3-8). A new section with another number costs as much as a few bars of clear evidence and needs at least 4 bars. The evidence for "this beat starts a bar" is the same term the first pass uses, so a song in one meter gets exactly the bars it got before. The pass adds under 0.1 s.
2. **Real tempo changes.** The tempo octave is now enforced only when the decoded tempo spans about a factor of 2 (spread ≥ 1.95, was 1.6). The old limit cut off real tempo changes, e.g. a chorus at 132 BPM, a bridge at 76 and an accelerando to 140, and forced the whole song into one range.
3. **Stored grids are decoded again** once (analyzer `...+grid2`), from the stored network output, with the user's hints.

### Results

Regression set, decoder 1 → decoder 2 (mean per group):

| Group | Songs | Beats F | Bar starts F | 1-bar loop | 4-bar loop |
|---|---|---|---|---|---|
| Steady (one meter, steady tempo) | 146 | 0.895 → 0.894 | 0.822 → 0.823 | 0.750 → 0.753 | 0.743 → 0.746 |
| Tempo changes | 27 | 0.899 → 0.931 | 0.883 → 0.921 | 0.752 → 0.851 | 0.706 → 0.816 |
| Meter changes | 50 | 0.941 → 0.944 | 0.666 → 0.728 | 0.549 → 0.632 | 0.410 → 0.503 |

21 songs better by 0.05 or more in bar-start F-measure, none worse. Examples:

- **Score songs:** waltz verse with a rock chorus 0.55–0.58 → 0.96–0.99, verses in 3/4 0.72 → 1.00 and in 6/4 0.67 → 0.80–1.00, tempo jumps with an accelerando 0.77–0.83 → 0.95–0.96, accelerating waltz 0.70–0.82 → 0.78–1.00 (at all or 2 of the 3 tempi).
- **Harmonix songs:** *Critical Acclaim* 0.82 → 0.92, *My Curse* 0.83 → 0.91, *Wake Up Dead* 0.65 → 0.77, *Good Mourning / Black Friday* 0.78 → 0.89.
- **Steady songs:** all 991 GTZAN clips decode as before (bar starts F 0.780 → 0.779, 4-bar loop 0.687 → 0.686), and so do the steady score and Harmonix songs, except the ballad with a double-time section, which improves (0.67 → 0.78).

On the songs with changes ([test_beat_tracking.py](../experiments/test_beat_tracking.py), sets `score_changes`, `harmonix_changes`; bar starts F / 4-bar loop):

| Method | Score: meter sections | Score: bar cycles | Score: tempo changes | Harmonix: meter changes | Harmonix: tempo changes |
|---|---|---|---|---|---|
| Peak picking | 0.79 / 0.45 | 0.88 / 0.59 | 0.89 / 0.65 | 0.80 / 0.51 | 0.93 / 0.86 |
| madmom DBN | 0.62 / 0.29 | 0.62 / 0.33 | 0.90 / 0.73 | 0.70 / 0.53 | 0.93 / 0.88 |
| Decoder 1 | 0.62 / 0.28 | 0.61 / 0.32 | 0.77 / 0.35 | 0.68 / 0.51 | 0.88 / 0.80 |
| **Decoder 2** | 0.76 / 0.50 | 0.61 / 0.32 | 0.88 / 0.66 | 0.71 / 0.54 | 0.90 / 0.83 |

Peak picking still finds more bar starts on these songs, since it lets every bar have its own length. That is also why it fails on steady songs (*Cryin'*: 20 % wrong bars).

### Tried and dropped ([test_meter_sections.py](../experiments/test_meter_sections.py), [results](../experiments/results/meter_sections.json))

| Variant | Meter: bar F / 4-bar loop | Tempo: bar F / 4-bar loop | Steady: bar F | Songs broken |
|---|---|---|---|---|
| Decoder 1 | 0.666 / 0.410 | 0.883 / 0.706 | 0.822 | – |
| Sections, change cost 30 | 0.734 / 0.507 | 0.889 / 0.712 | 0.817 | swing score song |
| Sections, cost 40 / **50** / 60 | 0.728 / 0.725 / 0.717; 4-bar loop 0.503 / 0.499 / 0.487 | 0.889 / 0.712 | 0.822 | none |
| Sections with 2 beats per bar | 0.728 / 0.498 | 0.899 / 0.753 | 0.818 | 4 (ballad, *Banjo*, 2 classical clips) |
| Tempo octave only above 2.2 | 0.671 / 0.419 | 0.939 / 0.858 | 0.822 | ballad with a double-time section |
| **Decoder 2** (sections, cost 50, 3-8 beats; octave above 1.95) | 0.728 / 0.503 | 0.921 / 0.816 | 0.823 | none |
| + single odd bars (cost 20) | 0.765 / 0.528 | 0.923 / 0.819 | 0.820 | swing score song, a classical clip |
| + single odd bars, each confirmed by the next bars | 0.756 / 0.523 | 0.922 / 0.819 | 0.823 | swing, 6/8 folk, a classical clip |

Single odd bars help songs like *The Day I Tried to Live* (4/4 with 7-beat bars in between, 0.56 → 0.87) and the 4+4+4+3 cycle (0.65–0.71 → 0.78–0.91). They still break a swing song the decoder gets right. For about 14 s of it the network calls the true bar starts plain beats (evidence −7) and puts bar starts on beat 3 (+7). That looks exactly like a real 2/4 bar, so no test on the network output tells the two apart; only the rest of the song shows it is wrong.

### Still hard

- **Mixed /8 meters like *Pneuma*:** the network switches between counting eighths, quarters and dotted quarters in the verses, and its bar starts there are erratic. Both decoders give *Pneuma* 4/4 throughout. On the *Pneuma*-like score song, where the network does find the bar starts, both decoders stay at 0.54–0.59 (peak picking, which lets every bar have its own length: 0.66–0.95): with the quarter note as the beat, a 5/8 bar has no whole number of beats. A beat grid of uneven beats (3+3, 3+2 eighths) needs a different model, or the user.
- **Single odd bars and bar cycles** (4+4+4+3, 7+7+7+8): the bars after them can be shifted until the user moves the bar starts (‹ Bar start ›).
- **Sections shorter than about 8 bars** with a meter close to the main one: two meter changes cost more than the few wrong bar starts the main meter gives there.

These are what the user's sections and bar starts are for ([Guided grids](#guided-grids)).

## Guided grids

For songs the decoder cannot get right alone, the user describes them (`beat_guidance.py`; hints `sections` and `barStarts`):

- **Sections:** a section starts on a bar and lasts until the next one. It may have:
  - its **beats per bar**, or a **bar pattern** repeated from its start (e.g. 6+6+5+6+5+5 for the verse of *Pneuma*);
  - its own **tempo**, e.g. eighth notes at twice the song's tempo, so that 5/8 bars have whole beats.
- **Bar starts:** "a bar starts here", tapped while listening or set with ‹ Bar start ›.

**Why the beats are decoded again:** counting bars from a given bar start afterwards is not enough. Near a 2/4 bar the automatic search bends or adds beats to keep its 4/4, so a correct bar start then counts from wrong beats. So the hints become constraints of the same Viterbi search, now over bar cycles instead of meters:

- **A section** allows only its cycle and its tempo. Without a meter it keeps the meters the automatic grid found there: a bar start should not change the meter. Without a tempo it keeps near the automatic tempo (±30 %), which also makes the search faster.
- **A given bar start** must fall on a beat within 60 ms of it, and that beat starts a bar. Before it there may be an odd bar: shorter (if at least half a bar), or up to half a bar longer. An odd bar costs a little, so a regular bar wins where the music allows both.
- **A section start** begins the section's cycle. The tempo may jump there (from quarter to eighth notes, or a new tempo).

The automatic grid is kept and reused: a new hint costs only the guided search, about 1.3 s for a 6-minute song and 5 s for the 12-minute *Pneuma*.

**Measured with a simulated user** ([test_assisted_grid.py](../experiments/test_assisted_grid.py), [results](../experiments/results/assisted_grid.json); also part of the regression test). From the true bars of every song with answers, the simulated user:

- adds a section wherever the bars change: a run of at least 4 bars of one length gets its meter; a repeating cycle gets its pattern;
- gives a section its tempo only where the detected beats there are twice or half as fast;
- for "+ taps", also sets a bar start right after every single odd bar.

| Regression set | Songs | Automatic: bar starts F / 4-bar loop | Sections | Sections + taps | Hints per song |
|---|---|---|---|---|---|
| Meter changes | 50 | 0.728 / 0.503 | 0.926 / 0.878 | **0.952 / 0.911** | 5 / 8 |
| Tempo changes | 27 | 0.921 / 0.816 | 0.941 / 0.864 | 0.947 / 0.871 | 1.4 / 1.7 |
| Steady | 146 | 0.823 / 0.746 | 0.875 / 0.853 | 0.884 / 0.869 | 1 |

The *Pneuma*-like score songs go from 0.56–0.62 to 1.00 with one pattern section and the eighth-note tempo.

Two songs get worse with hints:

- a classical clip that was already wrong (0.17 → 0.10);
- a pop clip whose annotators count bars twice as long as the network hears them (0.67 → 0.14). With half the tempo, every second slow beat falls where the network hears a bar start, and the slow beats slide off it. For such a song, 8 beats per bar at the detected tempo is the hint that works.

What's left wrong is mostly wrong beats, not bars: a beat on the off-beat (reggae one-drop), or a beat skipped where the network strongly prefers another bar start (swing). A bar start set there fixes the bars after it.

**Tried and dropped:** letting a network bar start count as a plain beat at a small cost (helps when the user's bars are twice the network's): steady songs 0.88 → 0.86, and some songs broke.

### The grid editor

How users give those hints (*Edit beats & bars*, E), modelled on what practice and DJ tools do:

- [Capo](https://supermegaultragroovy.com/products/capo/help/mac/4.6/song-structure): tap the first beat of every bar while the song plays, check the grid with the metronome, sections that start on a bar. Its author says its detection "is unable to work with odd or changing time signatures", hence the manual tools.
- [Transcribe!](https://seventhstring.com/xscribe/overview.html): section, bar and beat markers tapped on the keyboard.
- [Logic Pro's Smart Tempo](https://support.apple.com/guide/logicpro/lgcp644481aa/mac): downbeat and time signature *hints* that make the detection try again, rather than a grid drawn by hand.
- DJ software ([Serato](https://support.serato.com/hc/en-us/articles/360001274936-Beatgrids)): set the downbeat, shift the grid.

**What the editor shows** (`GET /api/library/<id>/visual`, `visual.py`, computed once in ~2 s for a 12-minute video):

- **Section colors.** Similar music gets a similar color (timbre and harmony, PCA, hue), so sections tend to stand out and a returning chorus gets its color again. It is a hint, not a detector ([test_section_colors.py](../experiments/test_section_colors.py), 38 Harmonix songs, 426 section starts): 43 % of section starts are among a song's largest 20 % of color changes, against 27 % for random times. The color change at a section start ranks at the 70th percentile on average, against the 58th.
- **Spectrogram** with the grid's bar and beat lines: attacks show as vertical lines.
- **Bars as rows.** Every bar of the selected section is a row, as long as the bar lasts, with the beat detection's bar-start likelihood in yellow. When the bars are right, the rows look alike and the yellow marks sit at their left edge; a wrong bar sticks out. A grid shifted by one beat looks just as tidy in any picture of the audio, so only the yellow marks, or the click track, give that away.
- **Click track.** A click on every beat, higher on bar starts, scheduled on the Web Audio clock from the player's position. It follows the speed and the loop jump. In the browser test its clicks land on the beats (to the millisecond of the scheduling); the latency difference between the click and the video's own sound was not measured.

Edits apply at once on screen and go to the backend 0.7 s after the last one (taps come in bursts), one decoding at a time; Ctrl+Z undoes them.

## Timing

- **Spread:** detected beats are within ~3 ms of the true onsets on score songs (median spread), and ~8 ms against human annotations on real songs (which includes the annotators' own jitter).
- **Bias:** they sit 10–20 ms after sharp attacks, so the player starts a snapped loop 30 ms early to keep the first note's attack.

## Speed

- **Network:** about 9 s for a 4-minute song on a laptop CPU.
- **Decoding:** 1–4 s; a song with two tempo octaves is decoded three times. The meter-sections pass adds under 0.1 s.
- **New hints:** decode again in 0.3–2 s; with sections or bar starts (guided), 1–5 s.
- **Long videos:** for audio over ~25 minutes, the decoder tries only 3 and 4 beats per bar, to stay within 150 MB of memory.

## Reproduce

See [../experiments/README.md](../experiments/README.md), items 5-8 for the data. Then:

```
python make_score_songs.py %MT_DATA%/score_midi 3
python score_to_audio.py %MT_DATA%/score_songs %MT_DATA%/score_midi
python test_beat_tracking.py                       # all methods, all test sets found
python test_beat_tracking.py app --sets gtzan      # one method, one set
python test_beat_tracking.py beat_this_minimal madmom_dbn app_decoder1 app --sets score_changes,harmonix_changes --out beat_tracking_changes
python make_beat_regression_set.py                 # the backend's regression set
python test_meter_sections.py                      # decoder variants on it
```

Results: [beat_tracking.json](../experiments/results/beat_tracking.json) (decoder 1, all methods), [beat_tracking_changes.json](../experiments/results/beat_tracking_changes.json) (both decoders, peak picking and madmom on the change sets), [beat_tracking_sections.json](../experiments/results/beat_tracking_sections.json) (decoder 2, all sets), [meter_sections.json](../experiments/results/meter_sections.json).
