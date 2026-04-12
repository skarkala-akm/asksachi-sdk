"""Tests for asksachi_sdk.a2a — A2A HTTP+JSON primitives."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asksachi_sdk.a2a import (
    NDJSON_MEDIA_TYPE,
    AgentCardSpec,
    build_completed_task_with_text_artifact,
    create_minimal_a2a_http_json_router,
    extract_user_text_from_message,
)


# ── extract_user_text_from_message ────────────────────────────────────────────

def test_extract_user_text_concat_parts() -> None:
    msg = {"parts": [{"text": "hello"}, {"text": "world"}]}
    assert extract_user_text_from_message(msg) == "hello\nworld"


def test_extract_user_text_single_part() -> None:
    msg = {"parts": [{"text": "ping"}]}
    assert extract_user_text_from_message(msg) == "ping"


def test_extract_user_text_empty_parts() -> None:
    msg = {"parts": []}
    assert extract_user_text_from_message(msg) == ""


# ── build_completed_task_with_text_artifact ───────────────────────────────────

def test_build_completed_task_shape() -> None:
    task = build_completed_task_with_text_artifact(output_text="hi", artifact_name="Result")
    t = task["task"]
    assert t["status"]["state"] == "TASK_STATE_COMPLETED"
    parts = t["artifacts"][0]["parts"]
    assert any(p.get("text") == "hi" for p in parts)


# ── minimal A2A router ────────────────────────────────────────────────────────

def _make_client(runtime_reply: str = "pong") -> TestClient:
    card = AgentCardSpec(
        name="Test",
        description="d",
        version="0.1.0",
        workflow_id="test",
        skill_name="Test",
        skill_description="d",
    )
    router = create_minimal_a2a_http_json_router(runtime=lambda t: runtime_reply, card=card)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_agent_card_endpoint() -> None:
    c = _make_client()
    r = c.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = r.json()
    assert card["name"] == "Test"
    assert "skills" in card


def test_message_send_returns_completed_task() -> None:
    c = _make_client("pong")
    body = {"message": {"parts": [{"text": "ping"}]}}
    r = c.post("/message:send", json=body)
    assert r.status_code == 200
    task = r.json()["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    text = task["artifacts"][0]["parts"][0]["text"]
    assert text == "pong"


def test_message_send_ndjson_stream() -> None:
    c = _make_client("hello stream")
    body = {"message": {"parts": [{"text": "go"}]}}
    r = c.post("/message:send", json=body, headers={"Accept": NDJSON_MEDIA_TYPE})
    assert r.status_code == 200
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    last = json.loads(lines[-1])
    assert last["type"] == "complete"
    assert last["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
