"""Logging setup helpers."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from typing import TextIO


def configure_console_encoding(
    streams: Iterable[TextIO] | None = None,
) -> None:
    """Use UTF-8 for report/log output so multilingual headlines cannot crash."""

    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            # Redirected/test streams may not support runtime reconfiguration.
            continue


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide logging."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
