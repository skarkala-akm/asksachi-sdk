"""FastAPI app factory that mounts the minimal A2A HTTP+JSON router."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI

from asksachi_sdk.a2a.http_json import AgentCardSpec, create_minimal_a2a_http_json_router

log = logging.getLogger(__name__)

_REGISTER_ATTEMPTS = 3  # total tries before giving up
_REGISTER_RETRY_DELAY_SEC = 2.0  # pause between attempts (first attempt also delayed by this)


async def _register_with_asksachi(self_base_url: str) -> bool:
    """POST /v1/agents/register to AskSachi.

    Returns ``True`` on success (201/409), ``False`` on transient failure.
    Raises on unexpected non-transient errors.
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
            "registered with AskSachi workflow_id=%s asksachi=%s",
            body.get("registered"),
            asksachi_url,
        )
        return True
    if r.status_code == 409:
        log.info("already registered with AskSachi asksachi=%s", asksachi_url)
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
    brief timing races between the two servers are handled automatically).
    """
    effective_self_url = (
        self_base_url
        or os.environ.get("ASKSACHI_WORKFLOW_BASE_URL", "").strip()
        or None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if effective_self_url:
            asyncio.create_task(_register_with_retry(effective_self_url))
        yield

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
