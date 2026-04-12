"""test-echo workflow — reference implementation using ``WorkflowSpec``."""

from __future__ import annotations

from asksachi_sdk.workflow_kit import workflow

# Hidden kickoff text sent by the UI when a user first opens this automation.
# Must match ``WORKFLOW_WELCOME_TRIGGER`` in app.js.
WORKFLOW_WELCOME_TRIGGER = "__ASKSACHI_WORKFLOW_WELCOME__"

_WELCOME_MD = """### Hello — quick sample

This is a **short built-in sample** so you can see how the **Automations** list works. \
Nothing here looks up the web for you—it simply shows that switching into a company flow is working.

**What happens next**
- Type anything you like in the box below.
- I'll repeat it back in plain language so you can tell this mode is active.

**Try it:** send a message when you're ready."""

spec = workflow(
    id="test-echo",
    title="Sample automation",
    description="A tiny built-in example so you can see how choosing an automation feels.",
    version="0.1.0",
    port=8766,
    tags=("echo", "sample", "demo"),
    examples=("Hello from another agent",),
    artifact_name="Echo result",
)


@spec.runtime
def run(user_text: str) -> str:
    """Welcome markdown for the UI trigger; plain echo for everything else."""
    if user_text.strip() == WORKFLOW_WELCOME_TRIGGER:
        return _WELCOME_MD
    return f"I heard you say: {user_text}"
