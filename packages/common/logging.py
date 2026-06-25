"""Structured logging setup for SupplyGuard."""

import sys

from loguru import logger


def setup_logging(*, debug: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[module]}</cyan> - "
            "<level>{message}</level>"
        ),
        enqueue=True,
    )


def get_logger(module: str):
    return logger.bind(module=module)
