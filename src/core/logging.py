import logging
import sys

from src.config import settings


def configure_logging() -> None:
    """
    Configure application-wide logging.
    """
    logging.basicConfig(
        level=settings.logging.level,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)