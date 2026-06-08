"""FastAPI app factory that mounts the minimal A2A HTTP+JSON router."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI

from asksachi_sdk.a2a.http_json import AgentCardSpec, create_minimal_a2a_http_json_router

log = logging.getLogger(__name__)

_REGISTER_ATTEMPTS = 3  # total tries before giving up on the *initial* registration
_REGISTER_RETRY_DELAY_SEC = 2.0  # pause between attempts (first attempt also delayed by this)
# AskSachi's agent registry is in-memory: when the gateway restarts it forgets every
# externally-registered workflow. Re-registering on an interval keeps us in the registry
# without anyone having to restart this workflow. 0 disables the heartbeat.
_HEARTBEAT_DEFAULT_SEC = 60.0


def _heartbeat_interval_sec() -> float:
    raw = os.environ.get("ASKSACHI_REGISTER_HEARTBEAT_SEC", "").strip()
    if not raw:
        return _HEARTBEAT_DEFAULT_SEC
    try:
        return max(0.0, float(raw))
    except ValueError:
        log.warning("invalid ASKSACHI_REGISTER_HEARTBEAT_SEC=%r — using default %ss", raw, _HEARTBEAT_DEFAULT_SEC)
        return _HEARTBEAT_DEFAULT_SEC


async def _register_with_asksachi(self_base_url: str, *, heartbeat: bool = False) -> bool:
    """POST /v1/agents/register to AskSachi.

    Returns ``True`` on success (200/201/409), ``False`` on transient failure.
    Raises on unexpected non-transient errors.

    When *heartbeat* is true the "already registered" (409) path logs at debug level
    so the periodic re-registration stays quiet; a fresh 200/201 still logs at info
    because it means the gateway had dropped us (e.g. after a restart) and we recovered.
    """
    asksachi_url = os.environ.get("ASKSACHI_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    api_key = os.environ.get("ASKSACHI_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            f"{asksachi_url}/v1/agents/register",
            json={"base_url": self_base_url},
            headers=headers,
        )
    if r.status_code in (200, 201):
        body = r.json()
        log.info(
            "%sregistered with AskSachi workflow_id=%s asksachi=%s",
            "re-" if heartbeat else "",
            body.get("registered"),
            asksachi_url,
        )
        return True
    if r.status_code == 409:
        log.debug("already registered with AskSachi asksachi=%s", asksachi_url) if heartbeat \
            else log.info("already registered with AskSachi asksachi=%s", asksachi_url)
        return True
    log.warning(
        "AskSachi registration unexpected status=%s asksachi=%s body=%s",
        r.status_code,
        asksachi_url,
        r.text[:200],
    )
    return False


async def _register_with_retry(self_base_url: str) -> None:
    """Retry registration up to ``_REGISTER_ATTEMPTS`` times with a fixed delay.

    The first attempt is also delayed so uvicorn has time to finish binding
    before AskSachi tries to fetch the agent card.
    """
    for attempt in range(1, _REGISTER_ATTEMPTS + 1):
        await asyncio.sleep(_REGISTER_RETRY_DELAY_SEC)
        try:
            if await _register_with_asksachi(self_base_url):
                return
        except Exception as exc:
            log.warning(
                "AskSachi registration attempt=%s/%s failed error=%s",
                attempt,
                _REGISTER_ATTEMPTS,
                exc,
            )
    log.warning(
        "AskSachi registration failed after %s attempts — "
        "register manually via POST /v1/agents/register base_url=%s",
        _REGISTER_ATTEMPTS,
        self_base_url,
    )


async def _register_loop(self_base_url: str) -> None:
    """Register on startup, then re-register on an interval forever.

    The interval keeps this workflow in AskSachi's in-memory registry across gateway
    restarts: when the gateway comes back empty, the next heartbeat re-registers us
    (within ``ASKSACHI_REGISTER_HEARTBEAT_SEC``, default 60s) — no manual restart needed.
    Cancelled cleanly on app shutdown.
    """
    await _register_with_retry(self_base_url)
    interval = _heartbeat_interval_sec()
    if interval <= 0:
        log.info("AskSachi registration heartbeat disabled (ASKSACHI_REGISTER_HEARTBEAT_SEC=0)")
        return
    while True:
        await asyncio.sleep(interval)
        try:
            await _register_with_asksachi(self_base_url, heartbeat=True)
        except Exception as exc:
            log.warning("AskSachi registration heartbeat failed error=%s", exc)


def create_text_workflow_a2a_app(
    *,
    title: str,
    description: str,
    version: str,
    runtime: Callable[[str], Any],
    card: AgentCardSpec,
    health_protocol_label: str = "A2A-HTTP+JSON-minimal",
    include_health: bool = True,
    self_base_url: str | None = None,
) -> FastAPI:
    """Return a **FastAPI** app with ``/.well-known/agent-card.json`` and ``POST /message:send``.

    If *self_base_url* is provided (or ``ASKSACHI_WORKFLOW_BASE_URL`` env var is set),
    the app registers itself with AskSachi on startup (retries up to 3 times so
    brief timing races between the two servers are handled automatically) and then
    re-registers on an interval (``ASKSACHI_REGISTER_HEARTBEAT_SEC``, default 60s) so
    it survives AskSachi gateway restarts without manual intervention.
    """
    effective_self_url = (
        self_base_url
        or os.environ.get("ASKSACHI_WORKFLOW_BASE_URL", "").strip()
        or None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task: asyncio.Task[None] | None = None
        if effective_self_url:
            task = asyncio.create_task(_register_loop(effective_self_url))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title=title, description=description, version=version, lifespan=lifespan)
    app.include_router(
        create_minimal_a2a_http_json_router(
            runtime=runtime,
            card=card,
            health_protocol_label=health_protocol_label,
            include_health=include_health,
        )
    )
    return app
