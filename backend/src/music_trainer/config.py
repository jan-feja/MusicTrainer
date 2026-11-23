"""Application settings.

Every setting can be overridden with an environment variable named
MUSIC_TRAINER_<SETTING>, e.g. MUSIC_TRAINER_DATA_DIR, or in a `.env` file in the
directory the server is started from.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/music_trainer/config.py -> repository root
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MUSIC_TRAINER_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000

    data_dir: Path = REPOSITORY_ROOT / "data"
    """Where downloaded videos, their analysis and stems, and model weights are stored."""

    frontend_dist_dir: Path = REPOSITORY_ROOT / "frontend" / "dist"
    """Built frontend; served at / when it exists (run `npm run build` in frontend/)."""

    max_video_height: int = Field(default=720, ge=144)
    """Highest video resolution to download, in pixels."""

    max_parallel_downloads: int = Field(default=2, ge=1)

    deno_path: Path | None = None
    """Deno executable for YouTube's JavaScript challenges; None = look it up on PATH."""

    ffmpeg_path: Path | None = None
    """ffmpeg executable or its folder; None = look it up on PATH."""

    beat_model: str = "final0"
    """Beat This! checkpoint: 'final0' (78 MB) or 'small0' (8 MB, faster); several separated
    by commas ('final0,final1,final2') are averaged: a little more accurate, 3x the time."""

    analysis_device: str = "cpu"
    """PyTorch device for beat detection: 'cpu' or 'cuda'."""

    analyze_beats_after_download: bool = True
    """Detect the beats of every new download right away, in the background."""

    stem_model: str = "htdemucs_6s"
    """Demucs model separating songs into stems: 'htdemucs_6s' (drums, bass, vocals, guitar,
    piano, other) or 'htdemucs' (drums, bass, vocals, other; slightly cleaner)."""

    separation_device: str = "cpu"
    """PyTorch device for stem separation: 'cpu' or 'cuda'."""

    separate_stems_after_download: bool = True
    """Separate every new download into stems right away (about 2 CPU minutes per song);
    otherwise only when the player opens the song."""

    session_days: float = Field(default=30, gt=0)
    """How long a login lasts without being used; using it extends it."""

    session_cookie_secure: bool = False
    """Send the login cookie over HTTPS only; turn on when the app is served over HTTPS."""

    guest_song_days: float = Field(default=7, ge=0)
    """A song no account has is deleted once no guest has opened it for this long."""

    @property
    def database_path(self) -> Path:
        """User accounts and their libraries (SQLite)."""
        return self.data_dir / "music_trainer.db"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def models_dir(self) -> Path:
        """Downloaded model weights."""
        return self.data_dir / "models"
