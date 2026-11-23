"""Separates one song into stems with Demucs; runs as its own process.

    python -m music_trainer.services.stem_worker <media file> <output folder> [--model ...]

Writes one FLAC per stem into the output folder and reports on stdout, one
line each: `PROGRESS <0-1>` while it runs and `RESULT <StemSet JSON>` at the
end. Errors go to stderr with a non-zero exit code.

A separate process because Demucs holds 1-2 GB of memory while it runs, which
is given back when the process ends, and the job can be stopped by ending it.
Measured in experiments/test_separation.py: htdemucs_6s takes about 2 minutes
for a 4-minute song on a laptop CPU.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from music_trainer.models import StemInfo, StemSet
from music_trainer.services.audio import AudioDecodeError, decode_audio, write_flac

PROGRESS_PREFIX = "PROGRESS "
RESULT_PREFIX = "RESULT "
MODEL_PREFIX = "demucs:"


def separate(
    media_path: Path,
    out_dir: Path,
    model_name: str,
    device: str = "cpu",
    ffmpeg: str = "ffmpeg",
    on_progress: Callable[[float], None] = lambda _: None,
) -> StemSet:
    # imports PyTorch: slow, so only here
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(model_name)
    model.eval()
    sample_rate = int(model.samplerate)
    samples = decode_audio(media_path, sample_rate, ffmpeg, channels=2)
    mix = torch.from_numpy(samples.T.copy())
    # Demucs expects the song normalised (as its own command line tool does)
    reference = mix.mean(0)
    mean, std = reference.mean(), reference.std() + 1e-8
    length = mix.shape[1]
    # the song is separated in segments of a few seconds; a bag holds one or more models
    segments = [float(m.segment) for m in getattr(model, "models", [model])]

    def report(state: dict) -> None:
        if state.get("state") != "end":
            return
        index = state["model_idx_in_bag"]
        segment_end = state["segment_offset"] + segments[index] * sample_rate
        on_progress((index + min(1.0, segment_end / length)) / len(segments))

    with torch.no_grad():
        separated = apply_model(
            model,
            ((mix - mean) / std)[None],
            shifts=1,
            split=True,
            overlap=0.25,
            device=device,
            progress=False,
            callback=report,
        )[0]
    separated = (separated * std + mean).cpu().numpy()

    stems = []
    for name, stem in zip(model.sources, separated, strict=True):
        file_name = f"{name}.flac"
        audio = stem.T  # (samples, channels)
        write_flac(out_dir / file_name, audio, sample_rate, ffmpeg)
        rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
        stems.append(StemInfo(name=name, file=file_name, rms=round(rms, 5)))
    return StemSet(
        model=f"{MODEL_PREFIX}{model_name}",
        sample_rate=sample_rate,
        duration=round(length / sample_rate, 3),
        stems=stems,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("media", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--model", default="htdemucs_6s")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)

    last = -1.0

    def on_progress(progress: float) -> None:
        nonlocal last
        if progress - last >= 0.01:  # at most 100 lines
            last = progress
            print(f"{PROGRESS_PREFIX}{progress:.3f}", flush=True)

    try:
        result = separate(
            args.media, args.out_dir, args.model, args.device, args.ffmpeg, on_progress
        )
    except AudioDecodeError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{RESULT_PREFIX}{result.model_dump_json()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
