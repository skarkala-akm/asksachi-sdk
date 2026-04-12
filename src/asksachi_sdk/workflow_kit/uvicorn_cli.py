"""Run a **FastAPI** app with uvicorn + ``--host`` / ``--port`` (typical ``serve`` console script)."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence

from fastapi import FastAPI


def ensure_asksachi_logging() -> None:
    """Configure the ``asksachi`` logger from ``ASKSACHI_LOG_LEVEL`` (default ``DEBUG``). Idempotent."""
    root_level = (os.environ.get("ASKSACHI_LOG_LEVEL") or "DEBUG").strip().upper()
    _configure_asksachi_logging(root_level)


def _configure_asksachi_logging(level_name: str) -> None:
    """Attach a stderr handler on ``asksachi`` so DEBUG lines work under uvicorn."""
    lvl = getattr(logging, level_name.upper(), logging.DEBUG)
    asksachi_log = logging.getLogger("asksachi")
    asksachi_log.setLevel(lvl)
    asksachi_log.propagate = False
    if not asksachi_log.handlers:
        h = logging.StreamHandler()
        h.setLevel(lvl)
        h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        asksachi_log.addHandler(h)


def _env_access_log(default: bool = True) -> bool:
    raw = (os.environ.get("UVICORN_ACCESS_LOG") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return default


def run_uvicorn_app(
    app: FastAPI,
    *,
    description: str = "Run HTTP server (uvicorn).",
    default_host: str = "127.0.0.1",
    default_port: int = 8766,
    log_level: str = "debug",
    argv: Sequence[str] | None = None,
) -> None:
    """Parse CLI args and call ``uvicorn.run`` (import **uvicorn** lazily).

    **Logging (stderr):**

    * ``UVICORN_LOG_LEVEL`` — overrides the default ``debug`` (e.g. ``info``, ``warning``).
    * ``UVICORN_ACCESS_LOG`` — ``0`` / ``false`` / ``off`` disables per-request access lines so
      Uvicorn / app messages are easier to spot; ``1`` / ``true`` forces them on.
    * ``ASKSACHI_LOG_LEVEL`` — stdlib root log level (default **DEBUG** unless set to e.g. ``INFO``).
    """
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--host", default=default_host)
    p.add_argument("--port", type=int, default=default_port)
    ns = p.parse_args(list(argv) if argv is not None else None)
    import uvicorn

    eff_level = (os.environ.get("UVICORN_LOG_LEVEL") or log_level).strip().lower() or "debug"
    ensure_asksachi_logging()
    uvicorn.run(
        app,
        host=ns.host,
        port=ns.port,
        log_level=eff_level,
        access_log=_env_access_log(),
    )
