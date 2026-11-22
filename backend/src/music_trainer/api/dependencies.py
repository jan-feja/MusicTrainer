"""Gives route handlers access to the services created at startup."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi import Path as PathParameter

from music_trainer.config import Settings
from music_trainer.services.beat_analysis import BeatAnalysisManager
from music_trainer.services.downloads import DownloadManager
from music_trainer.services.library import Library
from music_trainer.services.stem_separation import StemSeparationManager
from music_trainer.services.youtube import YouTubeClient
from music_trainer.video_ids import VIDEO_ID_PATTERN


@dataclass(frozen=True)
class Services:
    settings: Settings
    library: Library
    youtube: YouTubeClient
    downloads: DownloadManager
    beat_analysis: BeatAnalysisManager
    stem_separation: StemSeparationManager


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_settings(request: Request) -> Settings:
    return get_services(request).settings


def get_library(request: Request) -> Library:
    return get_services(request).library


def get_youtube(request: Request) -> YouTubeClient:
    return get_services(request).youtube


def get_downloads(request: Request) -> DownloadManager:
    return get_services(request).downloads


def get_beat_analysis(request: Request) -> BeatAnalysisManager:
    return get_services(request).beat_analysis


def get_stem_separation(request: Request) -> StemSeparationManager:
    return get_services(request).stem_separation


SettingsDependency = Annotated[Settings, Depends(get_settings)]
LibraryDependency = Annotated[Library, Depends(get_library)]
YouTubeDependency = Annotated[YouTubeClient, Depends(get_youtube)]
DownloadsDependency = Annotated[DownloadManager, Depends(get_downloads)]
BeatAnalysisDependency = Annotated[BeatAnalysisManager, Depends(get_beat_analysis)]
StemSeparationDependency = Annotated[StemSeparationManager, Depends(get_stem_separation)]
VideoIdParameter = Annotated[
    str, PathParameter(pattern=VIDEO_ID_PATTERN, description="YouTube video ID")
]
