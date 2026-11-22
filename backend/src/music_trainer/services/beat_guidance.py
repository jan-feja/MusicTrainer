"""Beat grids the user guides: sections with their own meter, bar pattern or tempo, and bar starts.

The automatic decoder (beat_decoding.py) assumes one meter per section of at least 4 bars and
finds those sections itself. Where the user knows better, their hints become constraints of
the same Viterbi search over (bar cycle, tempo, beat, frame), so the beats themselves follow
them too. (Counting bars from a given bar start afterwards is not enough: near a 2/4 bar the
automatic search bends or adds beats to keep its 4/4, and the count then starts off.)

- A **section** allows only its bar cycle: a meter (4) or a pattern of bar lengths (6, 6, 5,
  6, 5, 5); unset, the meters the automatic grid has there (a bar start the user gives should
  not change the meter). A section with a tempo allows only beats near it.
- A **bar start** (a section start, or a bar start the user tapped or set) must fall on a beat
  within FORCE_WINDOW of it, and that beat starts a bar. There the cycle may begin anew from
  any beat: an odd bar, or the next section's cycle. A section start begins its pattern; a
  tapped bar start may be any bar of it. At a section start the tempo may jump freely (to
  the next section's tempo, or from quarter to eighth notes).
- Without a tempo, a section keeps near the automatic grid's tempo there (fewer states, and
  fixing bars should not move the tempo).
"""

from dataclasses import dataclass

import numpy as np

from music_trainer.services import beat_decoding as bd

FORCE_WINDOW = 0.06  # s: a given bar start lands on a beat at most this far away
FORCED_BONUS = 50.0  # log-probability bonus for that bar start: worth many beats of evidence
TEMPO_MARGIN = 1.3  # without a given tempo, beats within this factor of the automatic ones'
MAX_GUIDED_POINTER_BYTES = 250_000_000
MIN_RELABEL_BEATS = 2 * bd.MIN_SECTION_BARS * min(bd.SECTION_METERS)  # room for a meter change
ODD_BAR_COST = 4.0  # an odd bar before a given bar start, against a full one (when both fit)
SHORT_BAR_COST = 20.0  # more if it is shorter than half a bar (one long bar is likelier)


@dataclass(frozen=True)
class _Span:
    start: int  # frame
    cycles: tuple[int, ...]  # indices into the plan's cycles
    tempo: tuple[float, float]  # allowed BPM range
    detected: bool  # no meter given: the automatic grid's meters


@dataclass(frozen=True)
class _Plan:
    cycles: tuple[tuple[int, ...], ...]  # bar lengths of every cycle; (4,) is plain 4/4
    spans: tuple[_Span, ...]
    forced: tuple[tuple[int, int, bool], ...]  # (first frame, end frame, cycle start only)


def decode_guided(
    beat_act: np.ndarray,
    bar_act: np.ndarray,
    fps: float,
    first: int,
    options: "bd.DecodingOptions",
    auto: "bd._Path",
    auto_positions: np.ndarray,
    allowed: tuple[float, float] | None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Beat frames and beats in bar under the user's sections and bar starts.

    `auto`, `auto_positions`: the automatic grid (its beats and their beats in bar).
    """
    plan = _plan(len(beat_act), fps, first, options, auto, auto_positions, allowed)
    path = _guided_viterbi(beat_act, bar_act, fps, plan)
    positions = path.beat_in_bar.copy()
    # in sections without a given meter, the meter may still change (as in automatic decoding),
    # between the bar starts the user gave (each one may follow an odd bar)
    window = round(FORCE_WINDOW * fps)
    forced_frames = np.array(sorted(lo + (hi - lo) // 2 for lo, hi, _ in plan.forced))
    starts = [span.start for span in plan.spans]
    for k, span in enumerate(plan.spans):
        if not span.detected:
            continue
        end = starts[k + 1] if k + 1 < len(starts) else len(beat_act)
        inside = np.flatnonzero((path.frames >= span.start) & (path.frames < end))
        if len(inside) < 2:
            continue
        frames = path.frames[inside]
        is_forced = np.zeros(len(frames), dtype=bool)
        if len(forced_frames):
            is_forced = (np.abs(frames[:, None] - forced_frames[None, :]) <= window).any(axis=1)
        cuts = sorted({0, *np.flatnonzero(is_forced).tolist()})
        for a, b in zip(cuts, [*cuts[1:], len(frames)], strict=True):
            if b - a < MIN_RELABEL_BEATS:  # too short for a meter change: the search's bars stay
                continue
            evidence = bd._evidence_at(frames[a:b], beat_act, bar_act)
            if is_forced[a]:
                evidence[0] += bd.FORCED_BAR_START
            positions[inside[a:b]] = bd._meter_sections(evidence)
    return path.frames, positions, {"guided": True, "log_prob": path.log_prob}


def _plan(
    n_frames: int,
    fps: float,
    first: int,
    options: "bd.DecodingOptions",
    auto: "bd._Path",
    auto_positions: np.ndarray,
    allowed: tuple[float, float] | None,
) -> _Plan:
    def frame(seconds: float) -> int:
        return int(np.clip(round(seconds * fps) - first, 0, n_frames - 1))

    cycles: list[tuple[int, ...]] = []

    def cycle_index(lengths: tuple[int, ...]) -> int:
        if lengths not in cycles:
            cycles.append(lengths)
        return cycles.index(lengths)

    bar_starts = np.flatnonzero(auto_positions == 0)
    bar_lengths = np.diff(bar_starts)

    def detected_cycles(lo: int, hi: int) -> tuple[int, ...]:
        """The meters of the automatic grid's bars that start in [lo, hi) (or the nearest bar)."""
        if options.beats_per_bar:
            return (cycle_index((options.beats_per_bar,)),)
        if len(bar_lengths) == 0:
            return tuple(cycle_index((m,)) for m in bd.METERS)
        frames = auto.frames[bar_starts[:-1]]
        inside = bar_lengths[(frames >= lo) & (frames < hi)]
        if len(inside) == 0:
            inside = bar_lengths[[min(int(np.searchsorted(frames, lo)), len(frames) - 1)]]
        return tuple(cycle_index((int(m),)) for m in sorted(set(inside.tolist())))

    def tempo_near_auto(lo: int, hi: int) -> tuple[float, float]:
        if options.tempo_bpm:
            return (options.tempo_bpm / bd.OCTAVE_SPAN, options.tempo_bpm * bd.OCTAVE_SPAN)
        bpm = auto.bpm[(auto.frames >= lo) & (auto.frames < hi)]
        if len(bpm) < 2:
            bpm = auto.bpm
        low, high = float(bpm.min()) / TEMPO_MARGIN, float(bpm.max()) * TEMPO_MARGIN
        if allowed is not None:
            low, high = max(low, allowed[0]), min(high, allowed[1])
        return (low, max(high, low * 1.05))

    window = round(FORCE_WINDOW * fps)
    sections = sorted(options.sections, key=lambda s: s.start)
    bounds = [frame(s.start) for s in sections]
    # a section's cycle may begin anywhere in the window around its start
    span_starts = [max(0, f - window) for f in bounds]
    spans = []
    if not span_starts or span_starts[0] > 0:
        end = span_starts[0] if span_starts else n_frames
        spans.append(_Span(0, detected_cycles(0, end), tempo_near_auto(0, end), True))
    for k, section in enumerate(sections):
        lo = span_starts[k]
        hi = span_starts[k + 1] if k + 1 < len(span_starts) else n_frames
        if hi <= lo:
            continue
        detected = not (section.pattern or section.beats_per_bar)
        if section.pattern:
            span_cycles: tuple[int, ...] = (cycle_index(tuple(section.pattern)),)
        elif section.beats_per_bar:
            span_cycles = (cycle_index((section.beats_per_bar,)),)
        else:
            span_cycles = detected_cycles(lo, hi)
        if section.tempo_bpm:
            tempo = (section.tempo_bpm / bd.OCTAVE_SPAN, section.tempo_bpm * bd.OCTAVE_SPAN)
        else:
            tempo = tempo_near_auto(lo, hi)
        spans.append(_Span(lo, span_cycles, tempo, detected))

    forced = {}
    for t in options.bar_starts:
        f = frame(t)
        forced[f] = (max(0, f - window), min(n_frames, f + window + 1), False)
    for f in bounds:  # a section start begins its cycle (wins over a tap at the same place)
        forced[f] = (max(0, f - window), min(n_frames, f + window + 1), True)
    windows = sorted(forced.values())
    merged: list[tuple[int, int, bool]] = []
    for lo, hi, cycle_start in windows:  # overlapping windows: keep the section start
        if merged and lo < merged[-1][1]:
            if cycle_start:
                merged[-1] = (lo, hi, True)
            continue
        merged.append((lo, hi, cycle_start))
    return _Plan(tuple(cycles), tuple(spans), tuple(merged))


def _guided_viterbi(
    beat_act: np.ndarray, bar_act: np.ndarray, fps: float, plan: _Plan
) -> "bd._Path":
    """bd._viterbi with the plan's constraints (see the module docstring)."""
    n_frames = len(beat_act)
    low = min(span.tempo[0] for span in plan.spans)
    high = max(span.tempo[1] for span in plan.spans)
    lengths = bd._tempo_grid(fps, (low, high))
    if len(lengths) == 0:
        lengths = bd._tempo_grid(fps, None)
    bpm_of = 60.0 * fps / lengths
    n_tempi = len(lengths)
    ratio = lengths[None, :] / lengths[:, None]
    tempo_change = -bd.TEMPO_CHANGE_COST * np.abs(ratio - 1)
    tempo_change -= np.log(np.exp(tempo_change).sum(axis=1, keepdims=True))

    # rows: every beat of every cycle; a bar starts at the cycle's bar offsets. A meter's bar
    # may also run on for up to half a bar ("long" rows): a longer bar before a given bar start
    rows: list[tuple[int, int]] = []
    bar_start_rows, cycle_start_rows, in_bar, bar_length = [], [], [], []
    for c, cycle in enumerate(plan.cycles):
        offsets = np.cumsum((0, *cycle[:-1]))
        for b in range(sum(cycle)):
            r = len(rows)
            rows.append((c, b))
            bar = int(np.searchsorted(offsets, b, side="right")) - 1
            in_bar.append(b - int(offsets[bar]))
            bar_length.append(cycle[bar])
            if b in offsets:
                bar_start_rows.append(r)
            if b == 0:
                cycle_start_rows.append(r)
        if len(cycle) == 1:
            for b in range(cycle[0], cycle[0] + (cycle[0] + 1) // 2):
                rows.append((c, b))
                in_bar.append(b)
                bar_length.append(cycle[0])
    if len(rows) * n_tempi * n_frames > MAX_GUIDED_POINTER_BYTES:
        raise ValueError("song too long for guided decoding with these sections")
    row_index = {row: r for r, row in enumerate(rows)}
    previous_row = np.array(
        [
            row_index[(c, b - 1)]
            if b >= sum(plan.cycles[c])
            else row_index[(c, (b - 1) % sum(plan.cycles[c]))]
            for c, b in rows
        ],
        dtype=np.int64,
    )
    # the bar that ends with a row, if a given bar start follows it: too short costs more
    odd_cost = np.array(
        [
            ODD_BAR_COST + (SHORT_BAR_COST if in_bar[r] + 1 < bar_length[r] / 2 else 0.0)
            for r in range(len(rows))
        ]
    )
    is_bar_row = np.zeros(len(rows), dtype=bool)
    is_bar_row[bar_start_rows] = True
    bar_end_rows = np.unique(previous_row[is_bar_row])  # last beats of bars
    row_cycle_of = np.array([c for c, _ in rows])
    long_rows = np.array(
        [r for r, (c, b) in enumerate(rows) if b >= sum(plan.cycles[c])], dtype=int
    )
    cycle_rows = [np.flatnonzero(row_cycle_of == c) for c in range(len(plan.cycles))]

    starts = np.zeros((len(rows), n_tempi), dtype=np.int64)
    ends = np.zeros_like(starts)
    kinds, state_row, state_tempo, state_offset = [], [], [], []
    offset = 0
    for r in range(len(rows)):
        for k, length in enumerate(lengths):
            starts[r, k], ends[r, k] = offset, offset + length - 1
            position = np.arange(length)
            on = position < length / bd.BEAT_WINDOW
            kinds.append(np.where(on, 2 if is_bar_row[r] else 1, 0))
            state_row.append(np.full(length, r))
            state_tempo.append(np.full(length, k))
            state_offset.append(position)
            offset += length
    kind = np.concatenate(kinds)
    row_of_state = np.concatenate(state_row)
    tempo_of_state = np.concatenate(state_tempo)
    is_beat_start = np.concatenate(state_offset) == 0

    # what may start a beat in each span: its cycles, its tempo range
    row_cycle = np.array([c for c, _ in rows])
    span_masks = []
    for span in plan.spans:
        tempo_ok = (bpm_of >= span.tempo[0] * 0.999) & (bpm_of <= span.tempo[1] * 1.001)
        if not tempo_ok.any():  # a range between two grid steps: the nearest tempo
            tempo_ok[np.argmin(np.abs(bpm_of - np.mean(span.tempo)))] = True
        mask = np.isin(row_cycle, span.cycles)[:, None] & tempo_ok[None, :]
        span_masks.append(np.where(mask, 0.0, -np.inf))
    span_of_frame = np.zeros(n_frames, dtype=int)
    for k, span in enumerate(plan.spans):
        span_of_frame[span.start :] = k
    forced_kind = np.zeros(n_frames, dtype=int)  # 0 free, 1 bar start, 2 cycle start
    for lo, hi, cycle_start in plan.forced:
        forced_kind[lo:hi] = 2 if cycle_start else 1
    targets = {1: np.array(bar_start_rows), 2: np.array(cycle_start_rows)}
    target_masks = {}
    for key, target in targets.items():
        mask = np.full((len(rows), n_tempi), -np.inf)
        mask[target] = FORCED_BONUS
        target_masks[key] = mask

    between = np.maximum((1 - beat_act - bar_act) / (bd.BEAT_WINDOW - 1), bd._EPSILON / 2)
    log_obs = np.log(np.stack([between, beat_act, bar_act], axis=1))
    on_beat, on_bar = np.flatnonzero(kind == 1), np.flatnonzero(kind == 2)
    beat_extra = log_obs[:, 1] - log_obs[:, 0]
    bar_extra = log_obs[:, 2] - log_obs[:, 0]

    tempo_pointer = np.zeros((n_frames, len(rows), n_tempi), dtype=np.uint8)
    row_pointer: dict[int, np.ndarray] = {}
    score = np.full(len(kind), -np.log(len(kind))) + log_obs[0][kind]
    first_mask = np.full(len(kind), -np.inf)
    first_mask[starts] = span_masks[span_of_frame[0]]
    for r in range(len(rows)):  # inside a beat at frame 0: allowed like its beat start
        for k in range(n_tempi):
            first_mask[starts[r, k] : ends[r, k] + 1] = span_masks[span_of_frame[0]][r, k]
    score += first_mask
    new = np.empty_like(score)
    row_axis, tempo_axis = np.arange(len(rows))[:, None], np.arange(n_tempi)[None, :]
    for t in range(1, n_frames):
        between_t = log_obs[t, 0]
        np.add(score[:-1], between_t, out=new[1:])
        if forced_kind[t] == 2:  # a section start: any tempo may follow
            candidates = np.broadcast_to(score[ends][:, :, None], (len(rows), n_tempi, n_tempi))
        else:
            candidates = score[ends][:, :, None] + tempo_change[None]
        best_from = candidates.argmax(axis=1)
        best = candidates[row_axis, best_from, tempo_axis]  # [row, to tempo]
        if forced_kind[t]:
            # a bar starts here: after the bar before ends (free), or after any beat at a small
            # cost (an odd bar, or a new cycle from the middle of a bar)
            tempi = np.arange(n_tempi)
            odd_scores = best - odd_cost[:, None]
            if forced_kind[t] == 2:  # a section start: the bar before may be of any cycle
                anywhere = np.broadcast_to(odd_scores.argmax(axis=0), (len(rows), n_tempi))
                ending = bar_end_rows[best[bar_end_rows].argmax(axis=0)]
                regular = np.broadcast_to(ending, (len(rows), n_tempi))
            else:  # a bar start inside a section: an odd bar of the same cycle, which goes on
                anywhere = np.empty((len(rows), n_tempi), dtype=np.int64)
                for members in cycle_rows:
                    anywhere[members] = members[odd_scores[members].argmax(axis=0)][None, :]
                regular = np.broadcast_to(previous_row[:, None], (len(rows), n_tempi))
            odd = odd_scores[anywhere, tempi[None, :]]
            regular_score = best[regular, tempi[None, :]]
            use_odd = odd > regular_score
            chosen = np.where(use_odd, anywhere, regular)
            value = np.where(use_odd, odd, regular_score)
            new[starts] = value + target_masks[forced_kind[t]] + between_t
            tempo_pointer[t] = best_from[chosen, tempi[None, :]]
            row_pointer[t] = chosen
        else:
            new[starts] = best[previous_row] + between_t
            tempo_pointer[t] = best_from[previous_row]
        new[starts] += span_masks[span_of_frame[t]]
        new[on_beat] += beat_extra[t]
        new[on_bar] += bar_extra[t]
        score, new = new, score

    # a long bar only ends at a given bar start, not with the song
    score[np.isin(row_of_state, long_rows)] = -np.inf
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
        before = row_pointer[t][r, k] if t in row_pointer else previous_row[r]
        state = int(ends[before, tempo_pointer[t, r, k]])

    frames = np.flatnonzero(is_beat_start[path])
    beat_rows = row_of_state[path[frames]]
    return bd._Path(
        frames=frames,
        beat_in_bar=np.array([in_bar[r] for r in beat_rows], dtype=int),
        bpm=bpm_of[tempo_of_state[path[frames]]],
        log_prob=log_prob,
    )
