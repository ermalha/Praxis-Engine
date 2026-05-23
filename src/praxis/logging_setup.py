"""Central structlog configuration for the Praxis CLI (D-047 / RW-019).

Routes structured-log console output to stderr (never stdout) so that
``praxis <cmd> --json | jq`` and similar pipelines stay clean. The
default minimum level is WARNING; set ``PRAXIS_DEBUG=1`` (handled by
the CLI entry point) to also surface DEBUG events to stderr.

This module deliberately has zero praxis imports so it can be safely
called at the very top of :mod:`praxis.cli` before any module that
performs ``structlog.get_logger()`` at import time is loaded.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, debug: bool = False) -> None:
    """Configure structlog: stderr-only sink, WARNING by default, DEBUG opt-in.

    Idempotent — safe to call multiple times. Each call rebuilds the
    configuration, which is useful for tests that need to switch between
    debug and quiet modes within one process.
    """
    level = logging.DEBUG if debug else logging.WARNING
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
