from __future__ import annotations

from asksachi_sdk.workflow_kit import workflow

spec = workflow(
    id="my-agent",
    title="My Agent",
    description="A simple AskSachi-compatible agent.",
    version="0.1.0",
    port=8766,
)


@spec.runtime
def run(user_text: str) -> str:
    return f"You said: {user_text}"


# Expose common surfaces
app = spec.build_app()  # FastAPI app (use with TestClient)
serve_main = spec.serve_main
cli_main = spec.cli_main
