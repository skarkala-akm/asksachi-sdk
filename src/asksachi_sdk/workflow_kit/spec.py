"""``WorkflowSpec`` — describe a workflow once, derive all surfaces from it.

Typical usage::

    from asksachi_sdk.workflow_kit import workflow

    spec = workflow(
        id="hello",
        title="Hello",
        description="Says hello back",
        version="0.1.0",
    )

    @spec.runtime
    def run(user_text: str) -> str:
        return f"Hello, {user_text}!"

Register with AskSachi chat (in ``bootstrap.py``)::

    r.register(spec.agent)

Expose as an A2A HTTP server (``pyproject.toml`` entry point)::

    serve_main = spec.serve_main   # callable at module level

Run as a CLI tool::

    cli_main = spec.cli_main
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowSpec:
    """Single description of a workflow — ``id``, ``title``, ``description``, ``version`` are all you need.

    Optional fields:

    - ``port``              — default uvicorn port for the A2A server (default 8766).
    - ``tags``              — searchable tags surfaced in the A2A agent card.
    - ``examples``          — example prompts shown in the agent card.
    - ``artifact_name``     — display name for the reply artifact (default ``"Result"``).
    - ``skill_description`` — finer-grained description for the A2A skill entry;
                              defaults to ``description`` when omitted.
    """

    id: str
    title: str
    description: str
    version: str = "0.1.0"
    port: int = 8766
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    artifact_name: str = "Result"
    skill_description: str = ""
    _fn: Callable[..., Any] | None = field(default=None, init=False, repr=False)

    def runtime(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator — register the runtime function (``user_text: str → reply``)."""
        self._fn = fn
        return fn

    def _require_fn(self) -> Callable[..., Any]:
        if self._fn is None:
            raise RuntimeError(
                f"WorkflowSpec {self.id!r}: no runtime registered — use @spec.runtime."
            )
        return self._fn

    @property
    def agent(self) -> "SimpleTextWorkflowAgent":  # type: ignore[name-defined]  # noqa: F821
        """Return a :class:`~asksachi_sdk.workflow_kit.chat_agent.SimpleTextWorkflowAgent` ready to register."""
        from asksachi_sdk.workflow_kit.chat_agent import SimpleTextWorkflowAgent

        return SimpleTextWorkflowAgent(
            workflow_id=self.id,
            title=self.title,
            description=self.description,
            version=self.version,
            reply=self._require_fn(),
        )

    def build_app(self, *, register_on_startup: bool = False) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
        """Build and return the A2A FastAPI app without starting uvicorn.

        Useful for testing (``TestClient(spec.build_app())``) and for building the
        app separately from running it.  Set *register_on_startup* to ``True`` to
        keep auto-registration with AskSachi; it is off by default so test clients
        don't fire network calls.
        """
        from asksachi_sdk.a2a import AgentCardSpec
        from asksachi_sdk.workflow_kit.a2a_app import create_text_workflow_a2a_app

        card = AgentCardSpec(
            name=self.title,
            description=self.description,
            version=self.version,
            workflow_id=self.id,
            skill_name=self.title,
            skill_description=self.skill_description or self.description,
            tags=self.tags,
            examples=self.examples,
            completed_artifact_name=self.artifact_name,
        )
        self_url = (
            os.environ.get("ASKSACHI_WORKFLOW_BASE_URL", f"http://127.0.0.1:{self.port}")
            if register_on_startup
            else None
        )
        return create_text_workflow_a2a_app(
            title=self.title,
            description=self.description,
            version=self.version,
            runtime=self._require_fn(),
            card=card,
            self_base_url=self_url,
        )

    def serve_main(self) -> None:
        """Entry point: build and run the A2A HTTP+JSON server with uvicorn.

        Reads ``ASKSACHI_WORKFLOW_BASE_URL`` (default ``http://127.0.0.1:{port}``) to
        know which URL to advertise when registering with AskSachi.
        """
        from asksachi_sdk.workflow_kit.uvicorn_cli import run_uvicorn_app

        run_uvicorn_app(self.build_app(register_on_startup=True), default_port=self.port)

    def cli_main(self) -> None:
        """Entry point: run the workflow as a CLI tool (reads ``-m`` / ``--message``)."""
        from asksachi_sdk.workflow_kit.cli import run_text_workflow_cli

        run_text_workflow_cli(
            description=self.description,
            runtime=self._require_fn(),
        )


def workflow(
    *,
    id: str,
    title: str,
    description: str,
    version: str = "0.1.0",
    port: int = 8766,
    tags: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
    artifact_name: str = "Result",
    skill_description: str = "",
) -> WorkflowSpec:
    """Create a :class:`WorkflowSpec` — the single object that drives all surfaces.

    Example::

        spec = workflow(id="qbr", title="Quarterly business review", description="…")

        @spec.runtime
        def run(user_text: str) -> str:
            return "Not yet implemented"
    """
    return WorkflowSpec(
        id=id,
        title=title,
        description=description,
        version=version,
        port=port,
        tags=tags,
        examples=examples,
        artifact_name=artifact_name,
        skill_description=skill_description,
    )
