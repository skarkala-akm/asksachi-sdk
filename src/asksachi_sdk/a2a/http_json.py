"""Minimal A2A **HTTP+JSON** surface shared by workflow agents.

Normative reference: https://a2a-protocol.org/latest/specification/

Provides:

- ``GET /.well-known/agent-card.json`` — Agent Card (camelCase JSON)
- ``POST /message:send`` — Send Message → completed ``Task`` with one text artifact

**Streaming (AskSachi extension):** if the client sends ``Accept: application/x-ndjson``,
the response body is **newline-delimited JSON** (``NDJSON``):

1. Zero or more ``{"type":"delta","text":"<chunk>"}`` lines (UTF-8 text fragments).
2. One final ``{"type":"complete","task":{...}}`` line where ``task`` matches the
   completed-task object returned in the non-streaming JSON body.

With any other ``Accept`` (for example ``application/a2a+json``), the handler returns
the original single JSON object (``application/a2a+json``).

Agents supply a synchronous **runtime** ``Callable[[str], str]`` or
``Callable[[str], Iterable[str]]`` (user text → reply text or iterable of text chunks).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

DEFAULT_CAPABILITIES: dict[str, bool] = {
    "streaming": True,
    "pushNotifications": False,
    "extendedAgentCard": False,
}

NDJSON_MEDIA_TYPE = "application/x-ndjson"
DEFAULT_STREAM_TEXT_CHUNK_CHARS = 32


def _iter_runtime_text_chunks(
    runtime: Callable[[str], Any],
    user_text: str,
    *,
    chunk_chars: int = DEFAULT_STREAM_TEXT_CHUNK_CHARS,
) -> Iterator[str]:
    """Turn ``runtime`` output into a stream of UTF-8 text fragments."""
    out = runtime(user_text)
    if isinstance(out, str):
        step = max(1, chunk_chars)
        for i in range(0, len(out), step):
            yield out[i : i + step]
        return
    for piece in out:
        yield str(piece)


def _ndjson_message_send_stream(
    *,
    runtime: Callable[[str], Any],
    user_text: str,
    artifact_name: str,
    chunk_chars: int,
) -> Iterator[bytes]:
    """NDJSON stream: deltas then one ``complete`` line (sync generator of bytes)."""
    pieces: list[str] = []
    for ch in _iter_runtime_text_chunks(runtime, user_text, chunk_chars=chunk_chars):
        pieces.append(ch)
        line = json.dumps({"type": "delta", "text": ch}, ensure_ascii=False) + "\n"
        yield line.encode("utf-8")
    full_text = "".join(pieces)
    task_root = build_completed_task_with_text_artifact(
        output_text=full_text,
        artifact_name=artifact_name,
    )
    final = json.dumps({"type": "complete", "task": task_root["task"]}, ensure_ascii=False) + "\n"
    yield final.encode("utf-8")


@dataclass(frozen=True)
class AgentCardSpec:
    """Metadata for ``/.well-known/agent-card.json`` and default artifact naming.

    ``workflow_id`` is used as ``skills[0].id`` in the agent card JSON and as the
    registry key when AskSachi registers a remote workflow.  It must match the
    ``workflow_id`` in your ``WorkflowSpec`` / ``SimpleTextWorkflowAgent``.
    """

    name: str
    description: str
    version: str
    workflow_id: str
    skill_name: str
    skill_description: str
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    protocol_version: str = "1.0"
    default_input_modes: tuple[str, ...] = ("text/plain",)
    default_output_modes: tuple[str, ...] = ("text/plain",)
    capabilities: dict[str, bool] | None = None
    completed_artifact_name: str = "Result"


def extract_user_text_from_message(message: dict[str, Any]) -> str:
    """Concatenate ``text`` parts from an A2A ``message`` object (best-effort)."""
    parts = message.get("parts") or []
    lines: list[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p and p["text"] is not None:
            lines.append(str(p["text"]))
    return "\n".join(lines)


def build_completed_task_with_text_artifact(
    *,
    output_text: str,
    artifact_name: str,
) -> dict[str, Any]:
    """Build a **completed** task JSON with a single ``text/plain`` artifact part."""
    task_id = str(uuid.uuid4())
    ctx_id = str(uuid.uuid4())
    art_id = str(uuid.uuid4())
    return {
        "task": {
            "id": task_id,
            "contextId": ctx_id,
            "status": {
                "state": "TASK_STATE_COMPLETED",
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            },
            "artifacts": [
                {
                    "artifactId": art_id,
                    "name": artifact_name,
                    "parts": [{"text": output_text, "mediaType": "text/plain"}],
                }
            ],
        }
    }


def build_agent_card_json(*, request: Request, card: AgentCardSpec) -> dict[str, Any]:
    """Agent Card payload (camelCase) for the HTTP+JSON binding."""
    base = str(request.base_url).rstrip("/")
    return {
        "name": card.name,
        "description": card.description,
        "version": card.version,
        "supportedInterfaces": [
            {
                "url": base,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": card.protocol_version,
            }
        ],
        "capabilities": dict(card.capabilities)
        if card.capabilities is not None
        else dict(DEFAULT_CAPABILITIES),
        "defaultInputModes": list(card.default_input_modes),
        "defaultOutputModes": list(card.default_output_modes),
        "skills": [
            {
                "id": card.workflow_id,
                "name": card.skill_name,
                "description": card.skill_description,
                "tags": list(card.tags),
                "examples": list(card.examples),
            }
        ],
    }


def invalid_message_send_body_response() -> JSONResponse:
    """RFC 7807-style JSON for a missing or invalid ``message`` field."""
    return JSONResponse(
        status_code=400,
        content={
            "type": "https://a2a-protocol.org/errors/invalid-argument",
            "title": "Invalid request",
            "status": 400,
            "detail": "Body must include a 'message' object.",
        },
        media_type="application/problem+json",
    )


def create_minimal_a2a_http_json_router(
    *,
    runtime: Callable[[str], Any],
    card: AgentCardSpec,
    include_health: bool = True,
    health_protocol_label: str = "A2A-HTTP+JSON-minimal",
    stream_text_chunk_chars: int = DEFAULT_STREAM_TEXT_CHUNK_CHARS,
) -> APIRouter:
    """Return a router with A2A routes; ``include_router(router)`` on your ``FastAPI`` app.

    **Runtime** — synchronous callable mapping user ``text`` to either a **str** (reply body)
    or an **iterable of str** fragments (streamed over NDJSON as deltas).
    """
    router = APIRouter()

    @router.get("/.well-known/agent-card.json")
    def agent_card(request: Request) -> JSONResponse:
        return JSONResponse(
            build_agent_card_json(request=request, card=card),
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @router.post("/message:send", response_model=None)
    def message_send(request: Request, body: dict[str, Any]) -> JSONResponse | StreamingResponse:
        msg = body.get("message")
        if not isinstance(msg, dict):
            return invalid_message_send_body_response()
        user_text = extract_user_text_from_message(msg)
        accept = (request.headers.get("accept") or "").lower()
        if NDJSON_MEDIA_TYPE in accept:
            return StreamingResponse(
                _ndjson_message_send_stream(
                    runtime=runtime,
                    user_text=user_text,
                    artifact_name=card.completed_artifact_name,
                    chunk_chars=stream_text_chunk_chars,
                ),
                media_type=NDJSON_MEDIA_TYPE,
                headers={"Cache-Control": "no-store"},
            )

        out = runtime(user_text)
        if isinstance(out, str):
            reply_text = out
        else:
            reply_text = "".join(str(x) for x in out)
        payload = build_completed_task_with_text_artifact(
            output_text=reply_text,
            artifact_name=card.completed_artifact_name,
        )
        return JSONResponse(payload, media_type="application/a2a+json")

    if include_health:

        @router.get("/health")
        def health() -> dict[str, str]:
            return {
                "status": "ok",
                "workflow": card.workflow_id,
                "protocol": health_protocol_label,
            }

    return router
