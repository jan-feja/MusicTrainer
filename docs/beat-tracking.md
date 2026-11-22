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
2. **One meter per song:** every bar has the same number of beats, 3 to 7. 2 is available only as a user hint.
3. **One tempo octave per song:** if the best grid mixes, say, 75 and 150 BPM, the song is decoded once per octave and the likelier one is kept.
4. **Click tracks:** if the network rates bar starts no higher than any other beat (e.g. a click track), there is no meter to find, so the grid gets 4 beats per bar.
5. **Precise timing:** beat times are refined to well below the network's 20 ms frames (parabolic peak, local straight-line fit).

The network output is stored with the video. The user's fixes (**hints**) therefore only decode again: a few seconds, or instantly for bar starts. The hints are:

- **½× / 2×:** the tempo octave (75 vs 150 BPM).
- **Beats per bar:** set the meter.
- **‹ Bar start ›:** move the bar starts one beat from the playhead on. This fixes the bars after a real odd bar and leaves the bars before it alone.
- **Steady:** space all beats exactly evenly, so every bar has the same length (for songs played to a click).

**Tried and dropped** (numbers in the experiment results):

- **Letting the meter change within a song:** at any cost it invented odd bars (15–37 % in some songs) and did not fix the real ones.
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

## Timing

- **Spread:** detected beats are within ~3 ms of the true onsets on score songs (median spread), and ~8 ms against human annotations on real songs (which includes the annotators' own jitter).
- **Bias:** they sit 10–20 ms after sharp attacks, so the player starts a snapped loop 30 ms early to keep the first note's attack.

## Speed

- **Network:** about 9 s for a 4-minute song on a laptop CPU.
- **Decoding:** 1–3 s; a song with two tempo octaves is decoded three times.
- **New hints:** decode again in 0.3–2 s.
- **Long videos:** for audio over ~25 minutes, the decoder tries only 3 and 4 beats per bar, to stay within 150 MB of memory.

## Reproduce

See [../experiments/README.md](../experiments/README.md), items 5 and 6 for the data. Then:

```
python make_score_songs.py %MT_DATA%/score_midi 3
python score_to_audio.py %MT_DATA%/score_songs %MT_DATA%/score_midi
python test_beat_tracking.py                       # all methods, all test sets found
python test_beat_tracking.py app --sets gtzan      # one method, one set
```
