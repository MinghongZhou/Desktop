"""Structured logging setup, shared by every entrypoint (backtest/paper/live)."""
from __future__ import annotations

import logging
import sys

import structlog

from robinhood_bot.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    level = getattr(logging, settings.level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.json_output
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
