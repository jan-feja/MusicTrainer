"""Separating a song into stems (drums, bass, vocals, guitar, piano, other) with Demucs.

Demucs (htdemucs_6s, MIT) runs in its own process, stem_worker.py; this module
starts it and reads its progress. Quality measured in experiments/test_separation.py
(docs/implementation-report.md, feature 10): vocals, drums and bass come out clean,
guitar fair, piano poorly.
"""

import collections
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from music_trainer.models import StemSet
from music_trainer.services.stem_worker import MODEL_PREFIX, PROGRESS_PREFIX, RESULT_PREFIX

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
_ERROR_LINES_KEPT = 20


class StemSeparationError(Exception):
    """Separation could not run or did not finish."""


class StemSeparator(Protocol):
    """Separates a media file into stems. Tests replace it with a fake."""

    @property
    def model(self) -> str:
        """Name of the separator, stored with the stems, e.g. 'demucs:htdemucs_6s'."""
        ...

    def separate(self, media_path: Path, out_dir: Path, on_progress: ProgressCallback) -> StemSet:
        """Write the stems into `out_dir` (empty) and describe them."""
        ...

    def stop(self) -> None:
        """End a separation that is running; its `separate` raises StemSeparationError."""
        ...


class DemucsSeparator:
    """StemSeparator running stem_worker.py with Demucs in a child process.

    The model weights (about 80 MB for htdemucs_6s) are downloaded into
    `models_dir` on first use.
    """

    def __init__(
        self, model_name: str, models_dir: Path, device: str = "cpu", ffmpeg: str = "ffmpeg"
    ) -> None:
        self._model_name = model_name
        self._models_dir = models_dir
        self._device = device
        self._ffmpeg = ffmpeg
        self._processes: set[subprocess.Popen[str]] = set()
        self._stopped: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    @property
    def model(self) -> str:
        return f"{MODEL_PREFIX}{self._model_name}"

    def separate(self, media_path: Path, out_dir: Path, on_progress: ProgressCallback) -> StemSet:
        command = [
            *(sys.executable, "-m", "music_trainer.services.stem_worker"),
            *(str(media_path), str(out_dir)),
            *("--model", self._model_name, "--device", self._device, "--ffmpeg", self._ffmpeg),
        ]
        env = {
            **os.environ,
            # keep the weights with the app's other models, not in the user's cache
            "HF_HUB_CACHE": str(self._models_dir / "huggingface"),
            "TORCH_HOME": str(self._models_dir / "torch"),
        }
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # one pipe: two could fill up and block
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except OSError as error:
            raise StemSeparationError(f"Could not start the separation: {error}") from error
        with self._lock:
            self._processes.add(process)
        result: StemSet | None = None
        other_lines: collections.deque[str] = collections.deque(maxlen=_ERROR_LINES_KEPT)
        try:
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip()
                if line.startswith(PROGRESS_PREFIX):
                    on_progress(float(line.removeprefix(PROGRESS_PREFIX)))
                elif line.startswith(RESULT_PREFIX):
                    result = StemSet.model_validate_json(line.removeprefix(RESULT_PREFIX))
                elif line:
                    other_lines.append(line)
            exit_code = process.wait()
        except (ValueError, ValidationError) as error:
            process.kill()
            raise StemSeparationError(f"Unexpected output from the separation: {error}") from error
        finally:
            with self._lock:
                self._processes.discard(process)
                stopped = process in self._stopped
                self._stopped.discard(process)
        if stopped:
            raise StemSeparationError("Separation was stopped")
        if exit_code != 0 or result is None:
            for line in other_lines:
                logger.warning("stem separation: %s", line)
            detail = other_lines[-1] if other_lines else f"exit code {exit_code}"
            raise StemSeparationError(f"Separation failed: {detail}")
        return result

    def stop(self) -> None:
        with self._lock:
            for process in self._processes:
                self._stopped.add(process)
                process.kill()
