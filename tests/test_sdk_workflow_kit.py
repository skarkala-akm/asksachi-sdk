"""Tests for asksachi_sdk.workflow_kit — WorkflowSpec, SimpleTextWorkflowAgent, helpers."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from asksachi_sdk.models_openai import ChatCompletionRequest, ChatMessage
from asksachi_sdk.workflow_kit import (
    AgentCardSpec,
    SimpleTextWorkflowAgent,
    WorkflowSpec,
    create_text_workflow_a2a_app,
    run_text_workflow_cli,
    workflow,
)


# ── WorkflowSpec ──────────────────────────────────────────────────────────────

def test_workflow_spec_requires_runtime_before_use() -> None:
    spec = workflow(id="x", title="X", description="d")
    with pytest.raises(RuntimeError, match="no runtime registered"):
        _ = spec.agent


def test_workflow_spec_runtime_decorator_registers_fn() -> None:
    spec = workflow(id="greet", title="Greet", description="Says hi")

    @spec.runtime
    def run(text: str) -> str:
        return f"hi {text}"

    assert run("bob") == "hi bob"
    # calling via spec._require_fn should return the same fn
    assert spec._require_fn()("alice") == "hi alice"


def test_workflow_spec_defaults() -> None:
    spec = workflow(id="z", title="Z", description="desc")
    assert spec.version == "0.1.0"
    assert spec.port == 8766
    assert spec.artifact_name == "Result"


# ── SimpleTextWorkflowAgent ───────────────────────────────────────────────────

def _make_agent(reply: str = "ok") -> SimpleTextWorkflowAgent:
    return SimpleTextWorkflowAgent(
        workflow_id="t",
        title="T",
        description="d",
        version="0.1.0",
        reply=lambda text: reply,
    )


def test_agent_complete_chat_returns_reply() -> None:
    agent = _make_agent("pong")
    req = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="ping")],
    )
    result = asyncio.run(agent.complete_chat(req))
    assert result["choices"][0]["message"]["content"] == "pong"


def test_agent_stream_chat_yields_sse_chunks() -> None:
    agent = _make_agent("hi")
    req = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="hello")],
    )

    async def collect():
        return [chunk async for chunk in agent.stream_chat(req)]

    chunks = asyncio.run(collect())
    full = "".join(chunks)
    assert "hi" in full
    assert "[DONE]" in full


# ── run_text_workflow_cli ─────────────────────────────────────────────────────

def test_cli_prints_reply(capsys) -> None:
    run_text_workflow_cli(
        description="test",
        runtime=lambda t: f"echo:{t}",
        progress_labels=[],
        argv=["-m", "hello"],
    )
    captured = capsys.readouterr()
    assert "echo:hello" in captured.out


# ── create_text_workflow_a2a_app ──────────────────────────────────────────────

def test_a2a_app_agent_card_and_message_send() -> None:
    card = AgentCardSpec(
        name="Ping",
        description="Ping agent",
        version="0.1.0",
        workflow_id="ping",
        skill_name="Ping",
        skill_description="Replies pong",
    )
    app = create_text_workflow_a2a_app(
        title="Ping",
        description="Ping agent",
        version="0.1.0",
        runtime=lambda t: "pong",
        card=card,
    )
    c = TestClient(app)

    r = c.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    assert r.json()["name"] == "Ping"

    r2 = c.post("/message:send", json={"message": {"parts": [{"text": "ping"}]}})
    assert r2.status_code == 200
    assert r2.json()["task"]["status"]["state"] == "TASK_STATE_COMPLETED"


# ── registration heartbeat ────────────────────────────────────────────────────

def test_heartbeat_interval_parsing(monkeypatch) -> None:
    from asksachi_sdk.workflow_kit import a2a_app

    monkeypatch.delenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", raising=False)
    assert a2a_app._heartbeat_interval_sec() == a2a_app._HEARTBEAT_DEFAULT_SEC
    monkeypatch.setenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", "5")
    assert a2a_app._heartbeat_interval_sec() == 5.0
    monkeypatch.setenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", "0")  # disabled
    assert a2a_app._heartbeat_interval_sec() == 0.0
    monkeypatch.setenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", "nonsense")  # falls back
    assert a2a_app._heartbeat_interval_sec() == a2a_app._HEARTBEAT_DEFAULT_SEC


def test_register_loop_reregisters_on_interval(monkeypatch) -> None:
    """After the initial registration the loop keeps re-registering (survives gateway restart)."""
    from asksachi_sdk.workflow_kit import a2a_app

    calls: list[object] = []

    async def fake_retry(url: str) -> None:
        calls.append("initial")

    async def fake_register(url: str, *, heartbeat: bool = False) -> bool:
        calls.append(heartbeat)
        return True

    monkeypatch.setattr(a2a_app, "_register_with_retry", fake_retry)
    monkeypatch.setattr(a2a_app, "_register_with_asksachi", fake_register)
    monkeypatch.setenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", "0.02")

    async def run() -> None:
        task = asyncio.create_task(a2a_app._register_loop("http://self.svc"))
        await asyncio.sleep(0.12)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    assert calls[0] == "initial"
    assert calls.count(True) >= 2  # several heartbeat re-registrations happened


def test_register_loop_heartbeat_disabled_returns_after_initial(monkeypatch) -> None:
    from asksachi_sdk.workflow_kit import a2a_app

    calls: list[object] = []

    async def fake_retry(url: str) -> None:
        calls.append("initial")

    async def fake_register(url: str, *, heartbeat: bool = False) -> bool:  # pragma: no cover - must not run
        calls.append(heartbeat)
        return True

    monkeypatch.setattr(a2a_app, "_register_with_retry", fake_retry)
    monkeypatch.setattr(a2a_app, "_register_with_asksachi", fake_register)
    monkeypatch.setenv("ASKSACHI_REGISTER_HEARTBEAT_SEC", "0")  # disabled → loop exits

    asyncio.run(asyncio.wait_for(a2a_app._register_loop("http://self.svc"), timeout=1.0))

    assert calls == ["initial"]  # no heartbeat re-registration
