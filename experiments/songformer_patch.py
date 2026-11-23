"""Make SongFormer's inference run on a 6 GB GPU and keep its frame outputs.

SongFormer (github.com/aslp-lab/songformer) embeds whole songs (420 s windows) with MuQ and MusicFM.
With plain attention that needs far more than 6 GB and pages into shared memory (~220 s per song
on an RTX 3060 laptop). This script, run once in a SongFormer checkout (Linux / WSL), writes
src/SongFormer/infer/infer_mt.py, a copy of infer.py that:
  - builds MuQ and MusicFM with their flash-attention conformers (memory grows linearly), MuQ's
    weights loaded with the weight-norm keys renamed and strictly checked;
  - runs the two embedders in bfloat16 (weights and autocast; float16 overflows: NaN, no
    boundaries) and SongFormer's own head in float32;
  - saves the frame outputs (<song>.npz: boundary and label logits, 8.333 frames/s) next to the
    JSON, for experiments/test_structure.py songformer_bars;
  - logs full tracebacks.
On the check song its sections were identical to the stock script's, at ~60-85 s per song.
It also fixes two incompatibilities with current libraries (torch.load weights_only, the
transformers.deepspeed import).

Usage: python songformer_patch.py <SongFormer checkout>
Then (in src/SongFormer, PYTHONPATH=../third_party): python infer/infer_mt.py -i list.scp -o out_dir
  --model SongFormer --checkpoint SongFormer.safetensors --config_path SongFormer.yaml -gn 1 -tn 1
"""

import sys
from pathlib import Path


def replace(text: str, old: str, new: str, what: str) -> str:
    if old not in text:
        raise SystemExit(f"cannot patch {what}: code not found (another SongFormer version?)")
    return text.replace(old, new)


def main() -> None:
    root = Path(sys.argv[1]) / "src"
    fm = root / "third_party" / "musicfm" / "model" / "musicfm_25hz.py"
    s = fm.read_text()
    if "weights_only=False" not in s:
        fm.write_text(replace(s, "torch.load(model_path)", "torch.load(model_path, weights_only=False)", "MusicFM loading"))
    flash = root / "third_party" / "musicfm" / "modules" / "flash_conformer.py"
    s = flash.read_text()
    old = "from transformers.deepspeed import is_deepspeed_zero3_enabled\n"
    if "transformers.integrations.deepspeed" not in s:
        flash.write_text(replace(s, old, "try:\n    " + old + "except ImportError:\n"
                                 "    from transformers.integrations.deepspeed import is_deepspeed_zero3_enabled\n", "deepspeed import"))

    src = root / "SongFormer" / "infer" / "infer.py"
    s = src.read_text()
    s = "import traceback\n" + s
    s = replace(s, 'MUSICFM_HOME_PATH = os.path.join("ckpts", "MusicFM")',
                'import sys\nsys.path.insert(0, os.path.abspath(os.path.join("..", "third_party", "musicfm")))  # modules.flash_conformer\n'
                'MUSICFM_HOME_PATH = os.path.join("ckpts", "MusicFM")', "module path")
    s = replace(s, '    muq = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter")\n', '''    _base = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter")
    _cfg = _base.config
    _cfg.is_flash = True
    muq = MuQ(_cfg)
    _sd = {k.replace("parametrizations.weight.original0", "weight_g").replace("parametrizations.weight.original1", "weight_v"): v
           for k, v in _base.state_dict().items()}
    muq.load_state_dict(_sd, strict=True)
    del _base
''', "MuQ loading")
    s = replace(s, "        is_flash=False,\n        stat_path", "        is_flash=True,\n        stat_path", "MusicFM flash")
    # conv front-ends and conformers stored in bfloat16 (the mel front-ends stay float32)
    s = replace(s, "    muq = muq.to(device).eval()\n", "    muq = muq.to(device).eval()\n"
                "    muq.model.conv.to(torch.bfloat16)\n    muq.model.conformer.to(torch.bfloat16)\n", "MuQ bf16")
    s = replace(s, "    musicfm = musicfm.to(device)\n", "    musicfm = musicfm.to(device)\n"
                "    musicfm.conv.to(torch.bfloat16)\n    musicfm.conformer.to(torch.bfloat16)\n", "MusicFM bf16")
    s = replace(s, "    with torch.no_grad():\n        while True:",
                '    with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):\n        while True:', "autocast")
    # SongFormer's head in float32
    lines = s.split("\n")
    i = next(k for k, line in enumerate(lines) if "msa_info, chunk_logits = model.infer(" in line)
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    depth, j = 0, i
    while True:
        depth += lines[j].count("(") - lines[j].count(")")
        if depth == 0:
            break
        j += 1
    lines[i: j + 1] = [indent + "embd = embd.float()", indent + 'with torch.autocast(device_type="cuda", enabled=False):'] + \
        ["    " + line for line in lines[i: j + 1]]
    s = "\n".join(lines)
    s = replace(s, "                msa_infer_output = postprocess_functional_structure(logits, hp)\n",
                '''                np.savez(os.path.join(args.output_dir, f"{Path(item).stem}.npz"),
                         function=logits["function_logits"][0].numpy().astype(np.float32),
                         boundary=logits["boundary_logits"][0].numpy().astype(np.float32))
                msa_infer_output = postprocess_functional_structure(logits, hp)
''', "saving frame outputs")
    s = replace(s, 'logger.error(f"process {rank} error\\n{item}\\n{e}")',
                'logger.error(f"process {rank} error\\n{item}\\n{traceback.format_exc()}")', "error log")
    (src.parent / "infer_mt.py").write_text(s)
    print("wrote", src.parent / "infer_mt.py")


if __name__ == "__main__":
    main()
