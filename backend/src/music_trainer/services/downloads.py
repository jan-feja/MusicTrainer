"""Background downloads: one job per video, run in a small thread pool."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from music_trainer.models import DownloadJob, DownloadStatus
from music_trainer.services.library import Library
from music_trainer.services.youtube import DownloadProgress, YouTubeClient, YouTubeError
from music_trainer.video_ids import require_valid_video_id

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    video_id: str
    title: str | None
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    error: str | None = None

    def snapshot(self) -> DownloadJob:
        return DownloadJob(
            video_id=self.video_id,
            status=self.status,
            progress=self.progress,
            title=self.title,
            error=self.error,
        )


class DownloadManager:
    """Starts downloads and keeps track of their progress.

    Jobs live in memory only; finished videos are found through the Library.
    """

    def __init__(self, youtube: YouTubeClient, library: Library, max_parallel: int = 2) -> None:
        self._youtube = youtube
        self._library = library
        self._executor = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="download")
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    def start(self, video_id: str, title: str | None = None) -> DownloadJob:
        """Start downloading, unless the video is already downloaded or downloading."""
        require_valid_video_id(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and job.status.is_active:
                return job.snapshot()
            if self._library.contains(video_id):
                job = _Job(video_id, title, DownloadStatus.COMPLETED, progress=1.0)
                self._jobs[video_id] = job
                return job.snapshot()
            job = _Job(video_id, title)
            self._jobs[video_id] = job
            self._executor.submit(self._run, job)
            return job.snapshot()

    def get(self, video_id: str) -> DownloadJob | None:
        require_valid_video_id(video_id)
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None:
                return job.snapshot()
        if self._library.contains(video_id):
            return DownloadJob(video_id=video_id, status=DownloadStatus.COMPLETED, progress=1.0)
        return None

    def list_jobs(self) -> list[DownloadJob]:
        with self._lock:
            return [job.snapshot() for job in self._jobs.values()]

    def forget(self, video_id: str) -> None:
        """Drop a finished job, e.g. after its video was deleted. Running jobs are kept."""
        with self._lock:
            job = self._jobs.get(video_id)
            if job is not None and not job.status.is_active:
                del self._jobs[video_id]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: _Job) -> None:
        self._update(job, status=DownloadStatus.DOWNLOADING)
        staging_dir = self._library.create_staging_dir(job.video_id)
        try:
            metadata = self._youtube.download(
                job.video_id, staging_dir, lambda progress: self._on_progress(job, progress)
            )
            self._library.commit(job.video_id, metadata)
        except YouTubeError as error:
            logger.info("Download of %s failed: %s", job.video_id, error)
            self._update(job, status=DownloadStatus.FAILED, error=str(error))
        except Exception:
            logger.exception("Download of %s failed unexpectedly", job.video_id)
            self._update(
                job,
                status=DownloadStatus.FAILED,
                error="Unexpected error while downloading; see the server log.",
            )
        else:
            self._update(job, status=DownloadStatus.COMPLETED, progress=1.0, title=metadata.title)
        finally:
            if job.status is not DownloadStatus.COMPLETED:
                self._library.discard_staging(job.video_id)

    def _on_progress(self, job: _Job, progress: DownloadProgress) -> None:
        status = (
            DownloadStatus.PROCESSING
            if progress.phase == "processing"
            else DownloadStatus.DOWNLOADING
        )
        # never let the bar move backwards (e.g. when a size estimate changes)
        self._update(job, status=status, progress=max(job.progress, progress.fraction))

    def _update(self, job: _Job, **changes: object) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(job, name, value)
