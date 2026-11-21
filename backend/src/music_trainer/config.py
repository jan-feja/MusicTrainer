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
    """Where downloaded videos (and later stems, analysis, ...) are stored."""

    frontend_dist_dir: Path = REPOSITORY_ROOT / "frontend" / "dist"
    """Built frontend; served at / when it exists (run `npm run build` in frontend/)."""

    max_video_height: int = Field(default=720, ge=144)
    """Highest video resolution to download, in pixels."""

    max_parallel_downloads: int = Field(default=2, ge=1)

    deno_path: Path | None = None
    """Deno executable for YouTube's JavaScript challenges; None = look it up on PATH."""

    ffmpeg_path: Path | None = None
    """ffmpeg executable or its folder; None = look it up on PATH."""

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"
