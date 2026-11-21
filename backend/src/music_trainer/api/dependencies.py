"""Gives route handlers access to the services created at startup."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi import Path as PathParameter

from music_trainer.config import Settings
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library
from music_trainer.services.youtube import YouTubeClient
from music_trainer.video_ids import VIDEO_ID_PATTERN


@dataclass(frozen=True)
class Services:
    settings: Settings
    library: Library
    youtube: YouTubeClient
    downloads: DownloadManager


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_library(request: Request) -> Library:
    return get_services(request).library


def get_youtube(request: Request) -> YouTubeClient:
    return get_services(request).youtube


def get_downloads(request: Request) -> DownloadManager:
    return get_services(request).downloads


LibraryDependency = Annotated[Library, Depends(get_library)]
YouTubeDependency = Annotated[YouTubeClient, Depends(get_youtube)]
DownloadsDependency = Annotated[DownloadManager, Depends(get_downloads)]
VideoIdParameter = Annotated[
    str, PathParameter(pattern=VIDEO_ID_PATTERN, description="YouTube video ID")
]
