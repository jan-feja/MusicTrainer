"""Transcribe audio files with YourMT3+ (multi-instrument, Chang et al. 2024) into MIDI.

YourMT3+ is not a pip package: it runs from the code of its Hugging Face Space
(huggingface.co/spaces/mimbres/YourMT3, Apache-2.0). Set YOURMT3_DIR
to a local copy of the Space with amt/src and the checkpoint of the model below.

Model: "YPTF.MoE+Multi (noPS)", the Space's default: Perceiver-TF encoder with mixture of
experts, multi-channel T5 decoder, 13 instrument classes (piano, chromatic percussion, organ,
guitar, bass, strings, brass, reed, pipe, synth lead, synth pad, singing voice, drums).

Usage: python yourmt3_runner.py <out_dir> <audio file or name::audio file ...>
  writes <out_dir>/<name or audio stem>.mid (General MIDI programs; drums on channel 10); files
  already there are skipped
"""

import os
import sys
import time
from collections import Counter
from pathlib import Path

YOURMT3_DIR = Path(os.environ["YOURMT3_DIR"])
sys.path.insert(0, str(YOURMT3_DIR / "amt" / "src"))
sys.path.insert(0, str(YOURMT3_DIR))

CHECKPOINT = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops@last.ckpt"
ARGS = [CHECKPOINT, "-p", "2024", "-tk", "mc13_full_plus_256", "-dec", "multi-t5", "-nl", "26",
        "-enc", "perceiver-tf", "-sqr", "1", "-ff", "moe", "-wf", "4", "-nmoe", "8", "-kmoe", "2",
        "-act", "silu", "-epe", "rope", "-rp", "1", "-ac", "spec", "-hop", "300", "-atc", "1", "-pr", "16"]


def load():
    os.chdir(YOURMT3_DIR)  # the Space resolves amt/logs/... relative to the working directory
    from model_helper import load_model_checkpoint

    return load_model_checkpoint(args=ARGS, device="cpu").to("cuda")


def transcribe(model, audio_path: Path, out_dir: Path, name: str, batch: int = 8) -> Path:
    import torch
    import torchaudio
    from utils.audio import slice_padded_array
    from utils.event2note import merge_zipped_note_events_and_ties_to_notes
    from utils.note2event import mix_notes
    from utils.utils import write_model_output_as_midi

    audio, sr = torchaudio.load(str(audio_path))
    audio = torch.mean(audio, dim=0).unsqueeze(0)
    audio = torchaudio.functional.resample(audio, sr, model.audio_cfg["sample_rate"])
    frames = model.audio_cfg["input_frames"]
    segments = slice_padded_array(audio, frames, frames)
    segments = torch.from_numpy(segments.astype("float32")).to("cuda").unsqueeze(1)
    with torch.no_grad():
        tokens, _ = model.inference_file(bsz=batch, audio_segments=segments)
    starts = [frames * i / model.audio_cfg["sample_rate"] for i in range(segments.shape[0])]
    notes_per_channel, errors = [], Counter()
    for ch in range(model.task_manager.num_decoding_channels):
        zipped, _, _ = model.task_manager.detokenize_list_batches([t[:, ch, :] for t in tokens], starts, return_events=True)
        notes, err = merge_zipped_note_events_and_ties_to_notes(zipped)
        notes_per_channel.append(notes)
        errors += err
    write_model_output_as_midi(mix_notes(notes_per_channel), str(out_dir), name, model.midi_output_inverse_vocab)
    written = out_dir / "model_output" / f"{name}.mid"
    target = out_dir / f"{name}.mid"
    written.replace(target)
    return target


def main() -> None:
    out_dir = Path(sys.argv[1]).resolve()
    jobs = []
    for arg in sys.argv[2:]:
        name, _, path = arg.rpartition("::")
        path = Path(path).resolve()
        jobs.append((name or path.stem, path))
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [(n, f) for n, f in jobs if not (out_dir / f"{n}.mid").exists()]
    if not todo:
        return
    model = load()
    for name, f in todo:
        t = time.time()
        transcribe(model, f, out_dir, name)
        print(f"{name}: {time.time() - t:.1f} s", flush=True)


if __name__ == "__main__":
    main()
