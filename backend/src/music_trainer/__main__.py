"""Start the server: `music-trainer` or `python -m music_trainer`."""

import logging

import uvicorn

from music_trainer.app import create_app
from music_trainer.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
