"""Common building blocks for **workflow** authors.

One ``runtime`` function ``user_text -> reply_text`` (sync, async, or a generator)
can drive any subset of these interaction surfaces:

- **AskSachi chat** — register ``spec.agent`` in ``bootstrap.py``
- **CLI**           — expose ``spec.cli_main`` as a ``[project.scripts]`` entry point
- **A2A HTTP+JSON** — expose ``spec.serve_main`` as a ``[project.scripts]`` entry point

Minimal example::

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

    # In bootstrap.py:  r.register(spec.agent)
    # In pyproject.toml:
    #   hello-serve = "my_package.hello_agent:spec.serve_main"
    #   hello-cli   = "my_package.hello_agent:spec.cli_main"
"""

from asksachi_sdk.a2a import (
    AgentCardSpec,
    build_agent_card_json,
    build_completed_task_with_text_artifact,
    create_minimal_a2a_http_json_router,
    extract_user_text_from_message,
)
from asksachi_sdk.workflow_kit.a2a_app import create_text_workflow_a2a_app
from asksachi_sdk.workflow_kit.chat_agent import SimpleTextWorkflowAgent, last_user_text
from asksachi_sdk.workflow_kit.cli import run_text_workflow_cli
from asksachi_sdk.workflow_kit.spec import WorkflowSpec, workflow
from asksachi_sdk.workflow_kit.uvicorn_cli import run_uvicorn_app

__all__ = [
    # ── New high-level API ─────────────────────────────────────
    "WorkflowSpec",
    "workflow",
    # ── Lower-level building blocks ────────────────────────────
    "AgentCardSpec",
    "SimpleTextWorkflowAgent",
    "build_agent_card_json",
    "build_completed_task_with_text_artifact",
    "create_minimal_a2a_http_json_router",
    "create_text_workflow_a2a_app",
    "extract_user_text_from_message",
    "last_user_text",
    "run_text_workflow_cli",
    "run_uvicorn_app",
]
