import pytest

from music_trainer.video_ids import (
    InvalidVideoIdError,
    is_valid_video_id,
    require_valid_video_id,
    video_id_from_url,
)


@pytest.mark.parametrize(
    "text",
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/watch?feature=share&v=jNQXAC9IVRw&t=10",
        "youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtu.be/jNQXAC9IVRw?si=abc",
        "https://m.youtube.com/watch?v=jNQXAC9IVRw",
        "https://music.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/shorts/jNQXAC9IVRw",
        "https://www.youtube.com/embed/jNQXAC9IVRw",
        "  https://www.youtube.com/live/jNQXAC9IVRw  ",
    ],
)
def test_video_id_from_url_accepts_youtube_links(text: str) -> None:
    assert video_id_from_url(text) == "jNQXAC9IVRw"


@pytest.mark.parametrize(
    "text",
    [
        "metallica one",
        "https://vimeo.com/watch?v=jNQXAC9IVRw",
        "https://www.youtube.com/watch?v=tooShort",
        "https://www.youtube.com/channel/UC4QobU6STFB0P71PMvOGN5A",
        "https://youtube.com.evil.example/watch?v=jNQXAC9IVRw",
    ],
)
def test_video_id_from_url_rejects_other_text(text: str) -> None:
    assert video_id_from_url(text) is None


@pytest.mark.parametrize("value", ["jNQXAC9IVRw", "a-b_c-d_e-f"])
def test_valid_ids(value: str) -> None:
    assert is_valid_video_id(value)
    assert require_valid_video_id(value) == value


@pytest.mark.parametrize("value", ["", "short", "jNQXAC9IVRw1", "../../etc/pa", "jNQXAC9IVR/"])
def test_invalid_ids(value: str) -> None:
    assert not is_valid_video_id(value)
    with pytest.raises(InvalidVideoIdError):
        require_valid_video_id(value)
