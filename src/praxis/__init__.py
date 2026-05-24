"""Praxis — an agent-led framework for IT business analysis."""

import os as _os

# D-047 / RW-019: configure structlog at package import. Several submodules
# call ``structlog.get_logger(...)`` at their module top-level; the default
# structlog factory writes to stdout, which corrupts ``praxis ... --json |
# jq`` pipelines. Configure once, here, before any submodule loads.
# Library consumers who want their own logging config can call
# ``structlog.configure(...)`` again after importing — structlog's
# configure() is idempotent and replaces prior settings.
from praxis.logging_setup import configure_logging as _configure_logging

_configure_logging(debug=_os.environ.get("PRAXIS_DEBUG") == "1")

from praxis.errors import PraxisError  # noqa: E402

__version__ = "1.0.0"
__all__ = ["PraxisError", "__version__"]
