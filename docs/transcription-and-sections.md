# Transcription and song sections: research and measurements

Follow-up to features 4, 5, 11, 12, 15, 16 and 17 of [implementation-report.md](implementation-report.md): notes and tabs for each instrument, key, chords, tuning, imported notation, and song sections (verse, chorus, solo, ...). Experiments: [../experiments/](../experiments/) (scripts named below); numbers: [../experiments/results/](../experiments/results/).

> **Status (23 November 2026):** draft. The laptop ran on battery during this work, which caps its GPU at 20 W (210 MHz); the GPU-bound runs (SongFormer on all test songs, YourMT3+ on the test songs, All-In-One, the string network) are queued for when it is plugged in. Sections marked *pending* are filled in then.

## Summary

| Function | Today in the app | Best option found | Measured | Recommendation |
|---|---|---|---|---|
| Song sections | none | SongFormer (2025) | *pending* (human agreement ceiling: 64 % of section starts within 0.5 s) | *pending* |
| Notes per instrument | none | YourMT3+ (one model, all instruments) vs Demucs + Basic Pitch | Demucs + Basic Pitch: 0.43 note F over all pitched notes, keys 0.10 | *pending* |
| Tabs (strings and frets) | none | fingering search (written here) | 58 % of notes on the guitarist's string (lowest-fret rule: 33 %) | use it; try audio-informed string choice (*pending*) |
| Notation (bars, rhythm) | none | beat-grid quantization → Guitar Pro 5 → alphaTab | 94–100 % of correctly transcribed notes at the exact score position | use it |
| Chords | chroma templates | madmom CNN + CRF | real guitar recordings: 58 % → 76 % of the time right | switch |
| Key | none | *pending* | *pending* | *pending* |
| Tuning | librosa | librosa | real recordings: median 4 cents off A440, 12 % more than 15 cents | keep; correct before transcribing (*pending*) |

## What exists in 2026

**Multi-instrument transcription**
- [YourMT3+](https://arxiv.org/abs/2407.04822) (Chang et al., MLSP 2024; [code and weights](https://huggingface.co/spaces/mimbres/YourMT3), Apache-2.0): one model for 13 instrument classes, including drums and singing voice. Not a pip package; it runs from the Space's code ([yourmt3_runner.py](../experiments/yourmt3_runner.py)). 561 MB checkpoint, ~36 s per song on this laptop's GPU when plugged in.
- [MuScriptor](https://huggingface.co/papers/2607.08168) (Mirelo / Kyutai, July 2026): the strongest open model reported so far (its model card: onset F 60.4 vs 32.5 for YourMT3+ on its benchmark). Inference code MIT, but the weights are **CC BY-NC 4.0 and gated** ([model card](https://huggingface.co/MuScriptor/muscriptor-large)): downloading needs a Hugging Face account that accepts the terms. Not tested here; worth testing with the user's token.
- [Basic Pitch](https://github.com/spotify/basic-pitch) (Apache-2.0) per separated stem, ADTOF for drums: the pipeline the implementation report planned.
- The [2025 AMT Challenge](https://arxiv.org/pdf/2603.27528) found multi-instrument transcription still far from solved: a YourMT3 variant ranked near the top, and scores drop sharply on dense mixes.

**Tabs**
- [TabCNN](https://ir.webis.de/anthology/people/a/andrew+wiggins/) (Wiggins & Kim, ISMIR 2019): audio → string and fret per frame, trained on GuitarSet. [Fretting-Transformer](https://arxiv.org/html/2506.14223v1) (2025) and [TART](https://arxiv.org/html/2510.02597v1) (2025) map MIDI to tab with transformers; neither has released weights.

**Song sections**
- [SongFormer](https://arxiv.org/abs/2510.02797) (ASLP-lab, 2025; [code](https://github.com/aslp-lab/songformer), [weights](https://huggingface.co/ASLP-lab/SongFormer)): MuQ and MusicFM self-supervised embeddings at 30 s and 420 s, boundaries and 8 labels (intro, verse, pre-chorus, chorus, bridge, instrumental, outro, silence). Trained on Harmonix and a large pseudo-labelled set.
- [All-In-One](https://github.com/mir-aidj/all-in-one) (Kim & Nam, WASPAA 2023; MIT): Demucs stems + neighbourhood attention; beats, bars and labelled sections, trained on Harmonix. Needs NATTEN (Linux only; its wheel server's certificate had expired, so it was built from source and patched).
- Classic baseline: Laplacian segmentation (McFee & Ellis 2014) in librosa.

**Key and chords**: madmom's CNN key classifier ([Korzeniowski & Widmer 2018](https://arxiv.org/abs/1808.05340)) and CNN + CRF chord recognizer; madmom's model files are CC BY-NC-SA.

## Test data

| Set | What | Answers | Used for |
|---|---|---|---|
| **SALAMI, Internet Archive part** (147 songs, ~6 min each) | live recordings, many genres, freely downloadable ([SALAMI](https://ddmal.music.mcgill.ca/research/salami)) | section functions by 1–2 annotators | sections; **no tested model was trained on it** |
| **Harmonix** (49 songs) | pop / rock, YouTube audio aligned to the annotations | sections, beats | sections; in SongFormer's and All-In-One's training data, so optimistic |
| **Score songs with stems** (28 songs, 41 min) | the beat-tracking score songs rendered again with every instrument's stem and exact notes ([render_score_stems.py](../experiments/render_score_stems.py)): drums, bass, clean and distorted guitars, keys, leads | exact notes, bars, section starts | transcription per instrument, notation, sections |
| **GuitarSet** (360 excerpts, 6 guitarists) | real acoustic guitar, microphone recording | notes with string and fret (hexaphonic pickup), chords, key | tabs, chords; guitarist 05 held out |
| **GTZAN** (837 excerpts with a key) | real recordings, 9 genres | key ([Kraft, Lerch & Zölzer](https://github.com/alexanderlerch/gtzan_key)) | key |

## Results

### Song sections
Metrics (mir_eval): **HR.5F / HR3F** = section starts found within 0.5 s / 3 s (F-measure); **PWF** = are repeated parts grouped alike; **ACC** = share of time with the right label (intro, verse, chorus, bridge, instrumental, outro, silence).

| Method | SALAMI HR.5F | HR3F | PWF | ACC | Harmonix HR.5F | HR3F |
|---|---|---|---|---|---|---|
| Laplacian (librosa) | 0.17 | 0.38 | 0.56 | – | 0.24 | 0.44 |
| Laplacian, snapped to bars | 0.25 | 0.39 | 0.56 | – | 0.25 | 0.46 |
| SongFormer | *pending* | | | | | |
| All-In-One | *pending* | | | | | |
| Second human annotator | **0.64** | **0.72** | **0.77** | **0.70** | – | – |

- The second annotator shows the ceiling: two experts agree on only 64 % of section starts (within 0.5 s) and 70 % of the labels.
- First SongFormer outputs (2 songs) had musically sensible sections but every boundary ~2 s early; decided at bar starts with a 2 s lag correction, one song went from 0.00 to 0.67 HR.5F. The lag correction is tuned on Harmonix only and tested on SALAMI and the score songs (*pending*).

### Notes per instrument (score songs)
Note F-measure: right pitch, onset within 50 ms. Drums: onset F per drum (kick, snare, hi-hat, toms, cymbals), averaged.

| Pipeline | All pitched | Bass | Guitar | Keys | Lead | Drums |
|---|---|---|---|---|---|---|
| Basic Pitch on the true stems (best case) | 0.66 | 0.63 | 0.67 | 0.40 | 0.80 | 0.97 |
| htdemucs_6s → Basic Pitch / ADTOF | 0.43 | 0.47 | 0.49 | 0.10 | 0.18 | 0.95 |
| BS-RoFormer-SW → Basic Pitch / ADTOF | *pending* | | | | | |
| YourMT3+ on the mix | *pending* | | | | | |
| htdemucs_6s → YourMT3+ per stem | *pending* | | | | | |

- Separation costs a third of the notes; keys and leads mostly vanish (Demucs's piano stem fails, as the implementation report found).
- Drums are close to perfect on synthetic drums; the ADTOF authors report ~0.88 on real recordings.

### Tabs (GuitarSet guitarist 05, real recordings)
| Notes from | Note F | Tab F (right string too) | Right string, of the notes found |
|---|---|---|---|
| the annotation (perfect notes) | 1.00 | 0.50 | 58 % |
| Basic Pitch | 0.81 | 0.38 | 55 % |
| YourMT3+ (first 9 excerpts) | 0.96 | 0.41 | 51 % |

- Both transcribers saw parts of GuitarSet in training, so their note scores are optimistic. The string choice is not learned by either.
- **The string is the bottleneck**: [tablature.py](../experiments/tablature.py) chooses strings by a fingering search (hand span, position, movement between chords; Viterbi), tuned on guitarists 00–04: 58 % on guitarist 05 vs 33 % for "lowest fret". Many "wrong" strings are equally playable alternatives; a guitarist would accept them, the metric does not.
- Next: hearing the string ([test_string_model.py](../experiments/test_string_model.py), a TabCNN-style network combined with the search; *pending*).

### Notation
[notation.py](../experiments/notation.py) places notes on the beat grid (sixteenths or triplets per beat), fills short gaps, splits notes at bar lines with ties, and writes Guitar Pro 5 (tab + notation for guitar and bass, percussion for drums). alphaTab renders it ([render_notation.py](../experiments/render_notation.py)).

| Notes | Bass | Guitar | Keys | Lead |
|---|---|---|---|---|
| played notes (quantization alone), share at the exact score position | 1.00 | 0.95 | 1.00 | 1.00 |
| htdemucs_6s + Basic Pitch: correctly found notes at the exact position | 0.97 | 0.87 | 0.91 | 0.99 |

With the score's own beats; with Beat This! beats: *pending*. Guitar loses a little because strummed chords are spread over ~30 ms.

### Chords (GuitarSet comping, 180 excerpts, real recordings)
| Method | Major / minor right (time) | Root right | Chord changes vs truth |
|---|---|---|---|
| the app today (CQT templates, per beat, Viterbi) | 0.58 | 0.63 | 0.71× |
| madmom CNN + CRF | **0.76** | **0.80** | 1.2× |

The app's detector was only ever tested on one synthetic song (98 %). On real playing with seventh chords and voicings it is right 58 % of the time; madmom's network is right 76 %.

### Tuning
- 196 real recordings (Harmonix + SALAMI): median 4 cents from A440; 12 % are more than 15 cents off, 7 % more than 25 cents ([test_tuning.py](../experiments/test_tuning.py)).
- librosa estimated synthetic detunings of ±25 / ±45 cents within 4 cents.
- Whether transcription needs the correction: *pending*.

### Key
*pending* ([test_key.py](../experiments/test_key.py): librosa with four key profiles, with and without drums removed, and madmom's CNN on GTZAN).

## Recommendations
*pending*

## Sources
- Chang et al., [YourMT3+](https://arxiv.org/abs/2407.04822), MLSP 2024; [Hugging Face Space](https://huggingface.co/spaces/mimbres/YourMT3)
- [MuScriptor paper](https://huggingface.co/papers/2607.08168) and [model card](https://huggingface.co/MuScriptor/muscriptor-large)
- [Results of the 2025 AMT Challenge](https://arxiv.org/pdf/2603.27528)
- Hao et al., [SongFormer](https://arxiv.org/abs/2510.02797); [code](https://github.com/aslp-lab/songformer)
- Kim & Nam, [All-In-One](https://arxiv.org/pdf/2307.16425v1.pdf), WASPAA 2023; [code](https://github.com/mir-aidj/all-in-one)
- Smith et al., [SALAMI](https://ddmal.music.mcgill.ca/research/salami), ISMIR 2011
- Korzeniowski & Widmer, [Genre-agnostic key classification with CNNs](https://arxiv.org/abs/1808.05340), ISMIR 2018
- [GTZAN key annotations](https://github.com/alexanderlerch/gtzan_key)
- Hamberger et al., [Fretting-Transformer](https://arxiv.org/html/2506.14223v1), 2025; [TART](https://arxiv.org/html/2510.02597v1), 2025
