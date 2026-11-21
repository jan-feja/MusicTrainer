"""YouTube video IDs: validation and extraction from URLs."""

import re
from urllib.parse import parse_qs, urlparse

VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"

_VIDEO_ID_RE = re.compile(VIDEO_ID_PATTERN)
_SHORT_LINK_HOSTS = {"youtu.be", "www.youtu.be"}
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
} | _SHORT_LINK_HOSTS
_ID_PATH_PREFIXES = ("/shorts/", "/embed/", "/live/", "/v/")


class InvalidVideoIdError(ValueError):
    def __init__(self, video_id: str) -> None:
        super().__init__(f"Invalid YouTube video ID: {video_id!r}")


def is_valid_video_id(value: str) -> bool:
    return _VIDEO_ID_RE.match(value) is not None


def require_valid_video_id(value: str) -> str:
    """Return the ID unchanged, or raise InvalidVideoIdError.

    IDs become folder names, so this also protects against path traversal.
    """
    if not is_valid_video_id(value):
        raise InvalidVideoIdError(value)
    return value


def video_id_from_url(text: str) -> str | None:
    """Return the video ID if `text` is a link to a YouTube video, otherwise None."""
    text = text.strip()
    if "://" not in text:
        text = f"https://{text}"
    url = urlparse(text)
    host = (url.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    if host in _SHORT_LINK_HOSTS:
        candidate = url.path.lstrip("/").split("/")[0]
    elif url.path == "/watch":
        candidate = parse_qs(url.query).get("v", [""])[0]
    else:
        candidate = next(
            (
                url.path.removeprefix(p).split("/")[0]
                for p in _ID_PATH_PREFIXES
                if url.path.startswith(p)
            ),
            "",
        )
    return candidate if is_valid_video_id(candidate) else None


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def default_thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
