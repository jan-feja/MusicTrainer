"""Beats and bars from frame-wise beat / bar-start probabilities (Viterbi decoding).

The beat network gives, 50 times per second, how likely a beat and a bar start
are. Picking the peaks alone lets every bar have its own length, and the result
breaks wherever the network hesitates: in a double-time section it suddenly
counts eighth notes, in a quiet passage it sees a bar start in the middle of a
bar. Music rarely does that, so this module finds the most likely beat grid
under a few musical assumptions (a bar-pointer model as in Krebs et al. 2015 and
Böck et al. 2016, the "DBN" of madmom, written here in numpy):

- tempo changes only gradually from beat to beat;
- bars have a meter: within a section every bar has the same number of beats,
  so bar starts cannot drift. The meter may change between sections (a verse
  in 3/4, a chorus in 4/4), but a section lasts at least 4 bars and every change
  costs as much as a few bars of clear evidence (_meter_sections). A single bar
  of another length is not allowed: the network's hesitations then turn into odd
  bars, and where it is confidently wrong for a few bars no test tells that
  apart from a real odd bar. 2 beats per bar only when the user says so;
- if the network rates bar starts no higher than other beats (a click track),
  there is no meter to find: 4 beats per bar;
- the tempo does not jump to its double or half: if the best grid spans about
  a factor of 2 (75 and 150 BPM), the song is decoded once per tempo octave and
  the more likely one is kept. Smaller spreads are real tempo changes and are
  followed.

A real single bar of another length (a 2/4 bar in a 4/4 song) therefore shifts
the bar starts after it; the user fixes that by saying where a bar starts
(place_bar_starts). Measured in experiments/test_beat_tracking.py and the
backend's regression set (tests/test_beat_regression.py); the user can also
override the meter and the tempo octave when the music is ambiguous.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np

FRAMES_PER_SECOND = 50  # Beat This! output rate
METERS = (3, 4, 5, 6, 7)  # beats per bar the decoder chooses from (2 only as a user hint:
# on GTZAN it turned 13 % of 4/4 songs into half bars, and real 2/4 is rare)
UNUSUAL_METER_COST = 2.0  # log-probability cost per bar of 5, 6 or 7 beats (GTZAN: meter right
# 93 -> 95 %, odd-meter test songs unchanged)
DEFAULT_METER = 4  # when the bar starts are no different from other beats (a click track)
MIN_BAR_CONTRAST = 0.15  # bar-start probability at bar starts minus at other beats
SECTION_METERS = (3, 4, 5, 6, 7, 8)  # beats per bar of a section (8: a 4/4 bar counted in eighths)
METER_CHANGE_COST = 50.0  # log-probability cost of a new section with another meter ...
MIN_SECTION_BARS = 4  # ... which lasts at least this many bars (tests/test_beat_regression.py)
LONG_INPUT_METERS = (3, 4)  # for inputs whose back pointers would exceed MAX_POINTER_BYTES
MAX_POINTER_BYTES = 150_000_000  # ~25 minutes of audio with all METERS
MIN_BPM, MAX_BPM = 55.0, 215.0  # tempo grid of the decoder (as in madmom)
TEMPO_STEPS = 60  # log-spaced tempi between MIN_BPM and MAX_BPM
TEMPO_CHANGE_COST = 100.0  # lambda: higher = steadier tempo
BEAT_WINDOW = 16.0  # the first 1/16 of a beat counts as "on the beat"
OCTAVE_CONFLICT = 1.95  # tempo spread (95th / 5th percentile) that means two tempo octaves (below:
# a real tempo change, e.g. 76 -> 140 BPM, which 1.6 used to cut off)
OCTAVE_SPAN = 1.4  # tempo range around a chosen octave: tempo / 1.4 .. tempo * 1.4
ACTIVITY_THRESHOLD = 0.05  # frames before the first / after the last activity this high are skipped
SMOOTHING_BEATS = 2  # beat times are fitted to a straight line over +-2 beats ...
SMOOTHING_LIMIT = 0.025  # ... where that moves them less than 25 ms (frames are 20 ms apart)
STEADY_OUTLIER = 0.04  # beats this far off the constant-tempo line do not pull it
_EPSILON = 1e-5


@dataclass(frozen=True)
class BeatActivations:
    """Frame-wise network output for one song: the decoder's input, stored to decode again."""

    beat: np.ndarray
    """Logit of "a beat is here", one value per frame."""
    downbeat: np.ndarray
    """Logit of "a bar starts here"."""
    fps: float
    model: str
    """Which network produced it, e.g. 'beat_this:final0'."""


@dataclass(frozen=True)
class DecodingOptions:
    """What the user knows about the song; None leaves it to the decoder."""

    beats_per_bar: int | None = None
    """Every bar has this many beats."""
    tempo_bpm: float | None = None
    """The tempo is near this (within a factor of 1.4): picks the tempo octave."""
    bar_starts: tuple[float, ...] = ()
    """Times where a bar starts; from each one on, bars are counted from there."""


@dataclass(frozen=True)
class DecodedBeats:
    beats: np.ndarray
    """Beat times in seconds, ascending."""
    downbeats: np.ndarray
    """Bar starts in seconds; each one is also a beat."""
    beats_per_bar: int | None
    """Number of beats per bar."""
    beat_in_bar: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    """Position of every beat in its bar, 0 = bar start."""
    info: dict = field(default_factory=dict, compare=False)
    """Diagnostics (log-probability, octave candidates)."""


def decode_beats(
    beat_logits: np.ndarray,
    downbeat_logits: np.ndarray,
    options: DecodingOptions = DecodingOptions(),
    fps: float = FRAMES_PER_SECOND,
) -> DecodedBeats:
    """Most likely beats and bar starts for the network's frame logits."""
    beat_act, bar_act = _activations(beat_logits, downbeat_logits)
    active = np.flatnonzero(np.maximum(beat_act, bar_act) >= ACTIVITY_THRESHOLD)
    if len(active) < 2:
        return DecodedBeats(np.array([]), np.array([]), None)
    first, last = int(active[0]), int(active[-1]) + 1
    beat_act, bar_act = beat_act[first:last], bar_act[first:last]

    meters = (options.beats_per_bar,) if options.beats_per_bar else METERS
    if len(beat_act) * sum(meters) * TEMPO_STEPS > MAX_POINTER_BYTES:
        meters = (options.beats_per_bar,) if options.beats_per_bar else LONG_INPUT_METERS
    info: dict = {}
    allowed = None
    if options.tempo_bpm:
        allowed = (options.tempo_bpm / OCTAVE_SPAN, options.tempo_bpm * OCTAVE_SPAN)
        path = _viterbi(beat_act, bar_act, fps, meters, allowed)
    else:
        path = _viterbi(beat_act, bar_act, fps, meters)
        slow, fast = _tempo_spread(path)
        if fast / slow > OCTAVE_CONFLICT:
            # two tempo octaves in one song (e.g. a double-time section): keep one of them
            ranges = [(t / OCTAVE_SPAN, t * OCTAVE_SPAN) for t in (slow, fast)]
            candidates = [_viterbi(beat_act, bar_act, fps, meters, r) for r in ranges]
            info["octaves"] = [
                (round(t, 1), round(c.log_prob, 1))
                for t, c in zip((slow, fast), candidates, strict=True)
            ]
            best = int(np.argmax([c.log_prob for c in candidates]))
            path, allowed = candidates[best], ranges[best]
    positions = path.beat_in_bar
    if not options.beats_per_bar:
        if _bar_contrast(path, bar_act) < MIN_BAR_CONTRAST:
            # bar starts look like any other beat (e.g. a click track): no meter to find
            path = _viterbi(beat_act, bar_act, fps, (DEFAULT_METER,), allowed)
            positions = path.beat_in_bar
            info["meter"] = "default"
        elif len(path.frames) > 1:
            positions = _meter_sections(_bar_evidence(path, beat_act, bar_act, fps))
    info["log_prob"] = path.log_prob

    times = _smooth((_refine(path.frames, beat_act + bar_act) + first) / fps)
    decoded = DecodedBeats(
        beats=times,
        downbeats=times[positions == 0],
        beats_per_bar=_most_common_bar_length(positions),
        beat_in_bar=positions,
        info=info,
    )
    return place_bar_starts(decoded, options.bar_starts)


def fit_steady_tempo(decoded: DecodedBeats) -> DecodedBeats:
    """All beats exactly evenly spaced: for songs played to a click.

    A straight line through the beat times (beats far off it are ignored, they are
    detection errors in a steady song). The bar starts stay on the same beats.
    """
    times = decoded.beats
    if len(times) < 4:
        return decoded
    index = np.arange(len(times))
    keep = np.ones(len(times), dtype=bool)
    for _ in range(3):
        slope, intercept = np.polyfit(index[keep], times[keep], 1)
        off = np.abs(times - (slope * index + intercept)) > STEADY_OUTLIER
        if off.all() or np.array_equal(~off, keep):
            break
        keep = ~off
    steady = slope * index + intercept
    return replace(decoded, beats=steady, downbeats=steady[decoded.beat_in_bar == 0])


def place_bar_starts(decoded: DecodedBeats, bar_starts: Sequence[float]) -> DecodedBeats:
    """Count the bars from each given bar start on (snapped to the nearest beat).

    The number of beats per bar stays (that of the section the start is in);
    only where the bars begin changes, from each given time to the end of its
    section (or the next given time). The bar before a given start ends early;
    if that leaves it shorter than half a bar, it joins the bar before it (one
    long bar is likelier than a one-beat bar), or becomes a pickup at the start.
    """
    if not bar_starts or len(decoded.beats) == 0 or not decoded.beats_per_bar:
        return decoded
    positions = decoded.beat_in_bar.copy()
    for start in sorted(bar_starts):
        first = int(np.argmin(np.abs(decoded.beats - start)))
        per_bar, end = _section_around(positions, first, decoded.beats_per_bar)
        positions[first:end] = np.arange(end - first) % per_bar
        earlier = np.flatnonzero(positions[:first] == 0)
        if len(earlier) and first - earlier[-1] < per_bar / 2:
            if len(earlier) > 1:  # merge into the bar before
                positions[earlier[-2] : first] = np.arange(first - earlier[-2])
            else:  # pickup before the first bar
                short = first - earlier[-1]
                positions[earlier[-1] : first] = per_bar - short + np.arange(short)
    return replace(
        decoded,
        downbeats=decoded.beats[positions == 0],
        beat_in_bar=positions,
        beats_per_bar=_most_common_bar_length(positions) or decoded.beats_per_bar,
    )


def _section_around(positions: np.ndarray, beat: int, default: int) -> tuple[int, int]:
    """Beats per bar of the bar around `beat`, and the beat where the next section starts."""
    starts = np.flatnonzero(positions == 0)
    lengths = np.diff(starts)
    if len(lengths) == 0:
        return default, len(positions)
    bar = max(0, int(np.searchsorted(starts, beat, side="right")) - 1)
    bar = min(bar, len(lengths) - 1)  # in the last (open) bar: the meter of the bar before
    per_bar = int(lengths[bar])
    following = bar
    while following < len(lengths) and lengths[following] == per_bar:
        following += 1
    end = len(positions) if following >= len(lengths) else int(starts[following])
    return per_bar, max(end, beat + 1)


@dataclass
class _Path:
    frames: np.ndarray  # frame of every beat
    beat_in_bar: np.ndarray  # 0 = bar start
    bpm: np.ndarray  # tempo at every beat
    log_prob: float


def _activations(
    beat_logits: np.ndarray, downbeat_logits: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Probabilities of "a beat that is not a bar start" and of "a bar start"."""
    beat = _sigmoid(np.asarray(beat_logits, dtype=np.float64)) * (1 - _EPSILON) + _EPSILON / 2
    bar = _sigmoid(np.asarray(downbeat_logits, dtype=np.float64)) * (1 - _EPSILON) + _EPSILON / 2
    return np.maximum(beat - bar, _EPSILON / 2), bar


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _tempo_grid(fps: float, allowed: tuple[float, float] | None) -> np.ndarray:
    """Beat lengths in frames, log-spaced from MIN_BPM to MAX_BPM.

    A tempo range selects part of the grid; a range beyond MIN_BPM..MAX_BPM extends
    it with the same spacing, so the tempo-change cost means the same everywhere.
    """
    step = (MAX_BPM / MIN_BPM) ** (1 / (TEMPO_STEPS - 1))
    slowest, fastest = MIN_BPM, MAX_BPM
    if allowed is not None:
        while slowest > allowed[0]:
            slowest /= step
        while fastest < allowed[1]:
            fastest *= step
    count = round(np.log(fastest / slowest) / np.log(step)) + 1
    bpm_grid = np.geomspace(slowest, fastest, count)
    lengths = np.unique(np.round(60.0 * fps / bpm_grid).astype(int))
    lengths = lengths[lengths >= 2]
    if allowed is not None:
        bpm = 60.0 * fps / lengths
        lengths = lengths[(bpm >= allowed[0]) & (bpm <= allowed[1])]
    return lengths


def _viterbi(
    beat_act: np.ndarray,
    bar_act: np.ndarray,
    fps: float,
    meters: tuple[int, ...],
    allowed: tuple[float, float] | None = None,
) -> _Path:
    """Most likely path through (meter, tempo, beat of the bar, frame within the beat).

    Within a beat the state moves one frame at a time; at the end of a beat it
    moves to the next beat of the bar (after the last one: the first) and the tempo
    may change, at a cost that grows with the tempo ratio. The meter never changes.
    Only beat starts store back pointers: every other state has exactly one
    predecessor, the previous frame of the same beat.
    """
    lengths = _tempo_grid(fps, allowed)
    n_tempi, n_frames = len(lengths), len(beat_act)
    ratio = lengths[None, :] / lengths[:, None]
    tempo_change = -TEMPO_CHANGE_COST * np.abs(ratio - 1)  # [from, to]
    tempo_change -= np.log(np.exp(tempo_change).sum(axis=1, keepdims=True))

    # a "row" is one beat of one meter; every row holds all tempi, every tempo `length` frames
    rows = [(m, b) for m, n in enumerate(meters) for b in range(n)]
    # entering a bar of an unusual length costs a little (per bar, so it scales like the evidence)
    entry_cost = np.array(
        [UNUSUAL_METER_COST if b == 0 and meters[m] >= 5 else 0.0 for m, b in rows]
    )[:, None]
    row_index = {row: r for r, row in enumerate(rows)}
    starts = np.zeros((len(rows), n_tempi), dtype=np.int64)
    ends = np.zeros_like(starts)
    kinds, state_row, state_tempo, state_offset = [], [], [], []
    offset = 0
    for r, (_, beat) in enumerate(rows):
        for k, length in enumerate(lengths):
            starts[r, k], ends[r, k] = offset, offset + length - 1
            position = np.arange(length)
            # 0 = between beats, 1 = on a beat, 2 = on a bar start
            kinds.append(np.where(position < length / BEAT_WINDOW, 2 if beat == 0 else 1, 0))
            state_row.append(np.full(length, r))
            state_tempo.append(np.full(length, k))
            state_offset.append(position)
            offset += length
    kind = np.concatenate(kinds)
    row_of_state = np.concatenate(state_row)
    tempo_of_state = np.concatenate(state_tempo)
    is_beat_start = np.concatenate(state_offset) == 0

    # the beat before each beat: the previous one of the bar, or the bar's last one
    previous_row = np.array([row_index[(m, (b - 1) % meters[m])] for m, b in rows], dtype=np.int64)

    between = np.maximum((1 - beat_act - bar_act) / (BEAT_WINDOW - 1), _EPSILON / 2)
    log_obs = np.log(np.stack([between, beat_act, bar_act], axis=1))
    # every state gets the "between beats" term; the few on-beat states get the difference on top
    on_beat, on_bar = np.flatnonzero(kind == 1), np.flatnonzero(kind == 2)
    beat_extra = log_obs[:, 1] - log_obs[:, 0]
    bar_extra = log_obs[:, 2] - log_obs[:, 0]

    tempo_pointer = np.zeros((n_frames, len(rows), n_tempi), dtype=np.uint8)
    score = np.full(len(kind), -np.log(len(kind))) + log_obs[0][kind]
    new = np.empty_like(score)
    row_axis, tempo_axis = np.arange(len(rows))[:, None], np.arange(n_tempi)[None, :]
    for t in range(1, n_frames):
        between_t = log_obs[t, 0]
        np.add(score[:-1], between_t, out=new[1:])  # one frame further into the beat
        candidates = score[ends][:, :, None] + tempo_change[None]  # [row, from tempo, to tempo]
        best_from = candidates.argmax(axis=1)
        best = candidates[row_axis, best_from, tempo_axis]
        new[starts] = best[previous_row] - entry_cost + between_t  # beat starts
        tempo_pointer[t] = best_from[previous_row]
        new[on_beat] += beat_extra[t]
        new[on_bar] += bar_extra[t]
        score, new = new, score

    state = int(score.argmax())
    log_prob = float(score[state])
    path = np.empty(n_frames, dtype=np.int64)
    for t in range(n_frames - 1, -1, -1):
        path[t] = state
        if t == 0:
            break
        if not is_beat_start[state]:
            state -= 1
            continue
        r, k = row_of_state[state], tempo_of_state[state]
        state = int(ends[previous_row[r], tempo_pointer[t, r, k]])

    frames = np.flatnonzero(is_beat_start[path])
    beat_rows = row_of_state[path[frames]]
    return _Path(
        frames=frames,
        beat_in_bar=np.array([rows[r][1] for r in beat_rows], dtype=int),
        bpm=60.0 * fps / lengths[tempo_of_state[path[frames]]],
        log_prob=log_prob,
    )


def _bar_evidence(path: _Path, beat_act: np.ndarray, bar_act: np.ndarray, fps: float) -> np.ndarray:
    """For every beat of the path: how much likelier the network finds a bar start than a beat.

    The same term as in _viterbi: log(bar) - log(beat) summed over the frames that
    count as "on the beat", so with one meter _meter_sections finds the same bars.
    """
    lengths = np.round(60.0 * fps / path.bpm).astype(int)
    ratio = np.log(bar_act) - np.log(beat_act)
    widths = np.ceil(lengths / BEAT_WINDOW).astype(int)
    return np.array([ratio[f : f + w].sum() for f, w in zip(path.frames, widths, strict=True)])


def _meter_sections(evidence: np.ndarray) -> np.ndarray:
    """Beat in bar of every beat, for bars that may change length between sections.

    Most likely labeling of the beats (given how likely each is a bar start) under:
    within a section every bar has the same number of beats (SECTION_METERS); a
    new section with another number costs METER_CHANGE_COST and is possible only
    after MIN_SECTION_BARS bars of the current one; bars of 5 beats or more cost
    UNUSUAL_METER_COST each, as in _viterbi. A state is (beats per bar, bars of
    the section before this one up to MIN_SECTION_BARS - 1, beat in bar).
    """
    full = MIN_SECTION_BARS - 1  # bars before the current one when the section may end with it
    states = [(m, c, q) for m in SECTION_METERS for c in range(full + 1) for q in range(m)]
    index = {state: i for i, state in enumerate(states)}
    meter = np.array([m for m, _, _ in states])
    count = np.array([c for _, c, _ in states])
    beat = np.array([q for _, _, q in states])
    inner = np.flatnonzero(beat > 0)
    inner_previous = np.array([index[(m, c, q - 1)] for m, c, q in (states[i] for i in inner)])
    starts, ends = np.flatnonzero(beat == 0), np.flatnonzero(beat == meter - 1)
    transition = np.full((len(ends), len(starts)), -np.inf)  # bar end -> next bar start
    for a, e in enumerate(ends):
        m, c, _ = states[e]
        for b, s in enumerate(starts):
            m_next, c_next, _ = states[s]
            if m_next == m and c_next == min(full, c + 1):
                cost = 0.0
            elif m_next != m and c == full and c_next == 0:
                cost = METER_CHANGE_COST
            else:
                continue
            transition[a, b] = -cost - (UNUSUAL_METER_COST if m_next >= 5 else 0.0)

    # start anywhere in a bar of any meter
    score = np.where(count == 0, np.where(beat == 0, evidence[0], 0.0), -np.inf)
    back = np.zeros((len(evidence), len(starts)), dtype=np.int16)
    columns = np.arange(len(starts))
    for i in range(1, len(evidence)):
        new = np.empty_like(score)
        new[inner] = score[inner_previous]
        candidates = score[ends][:, None] + transition
        best = candidates.argmax(axis=0)
        new[starts] = candidates[best, columns] + evidence[i]
        back[i] = best
        score = new

    state = int(score.argmax())
    labels = np.empty(len(evidence), dtype=int)
    start_column = {s: k for k, s in enumerate(starts)}
    for i in range(len(evidence) - 1, -1, -1):
        labels[i] = beat[state]
        if i == 0:
            break
        if beat[state] > 0:
            state = int(inner_previous[np.searchsorted(inner, state)])
        else:
            state = int(ends[back[i, start_column[state]]])
    return labels


def _bar_contrast(path: _Path, bar_act: np.ndarray) -> float:
    """How much likelier the network finds a bar start at the bar starts than at other beats."""
    is_bar_start = path.beat_in_bar == 0
    if is_bar_start.all() or not is_bar_start.any():
        return 1.0
    peaks = np.array([bar_act[max(0, f - 2) : f + 3].max() for f in path.frames])
    return float(peaks[is_bar_start].mean() - peaks[~is_bar_start].mean())


def _tempo_spread(path: _Path) -> tuple[float, float]:
    """5th and 95th percentile of the tempo, weighted by time."""
    if len(path.frames) < 8:
        return 1.0, 1.0
    durations = np.diff(path.frames, append=path.frames[-1] + 1).astype(float)
    order = np.argsort(path.bpm)
    share = np.cumsum(durations[order]) / durations.sum()
    pick = lambda q: float(path.bpm[order][min(len(order) - 1, int(np.searchsorted(share, q)))])  # noqa: E731
    return pick(0.05), pick(0.95)


def _refine(frames: np.ndarray, activation: np.ndarray) -> np.ndarray:
    """Sub-frame beat times: activation peak near each beat, parabolic interpolation."""
    times = frames.astype(np.float64)
    n = len(activation)
    for i, frame in enumerate(frames):
        lo, hi = max(0, frame - 2), min(n, frame + 3)
        peak = lo + int(np.argmax(activation[lo:hi]))
        if 0 < peak < n - 1:
            y0, y1, y2 = activation[peak - 1 : peak + 2]
            curvature = y0 - 2 * y1 + y2
            times[i] = peak + (
                float(np.clip(0.5 * (y0 - y2) / curvature, -0.5, 0.5)) if curvature < 0 else 0.0
            )
        else:
            times[i] = peak
    return times


def _smooth(times: np.ndarray) -> np.ndarray:
    """Average out frame jitter: fit beats to their neighbours where those keep a steady tempo."""
    smoothed = times.copy()
    for i in range(len(times)):
        lo, hi = max(0, i - SMOOTHING_BEATS), min(len(times), i + SMOOTHING_BEATS + 1)
        if hi - lo < 3:
            continue
        slope, intercept = np.polyfit(np.arange(lo, hi), times[lo:hi], 1)
        fitted = slope * i + intercept
        if abs(fitted - times[i]) < SMOOTHING_LIMIT:
            smoothed[i] = fitted
    return smoothed


def _most_common_bar_length(beat_in_bar: np.ndarray) -> int | None:
    """Beats per bar of most bars (a song with a single bar: its length so far)."""
    starts = np.flatnonzero(beat_in_bar == 0)
    if len(starts) == 0:
        return None
    if len(starts) == 1:
        return int(beat_in_bar.max()) + 1
    return int(np.bincount(np.diff(starts)).argmax())
