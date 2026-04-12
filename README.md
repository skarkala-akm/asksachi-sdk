# asksachi-sdk

Shared building blocks for AskSachi-compatible workflow agents.

Provides the **A2A HTTP+JSON primitives**, **WorkflowSpec**, and **CLI/server helpers** that every workflow agent needs. Both `asksachi` (core) and `qbr-workflow` depend on this package.

## What's inside

| Module | Purpose |
|--------|---------|
| `asksachi_sdk.a2a` | Agent Card, `message:send`, task/artifact shapes, NDJSON streaming |
| `asksachi_sdk.workflow_kit` | `WorkflowSpec` / `@workflow` decorator, `SimpleTextWorkflowAgent`, CLI + uvicorn helpers |
| `asksachi_sdk.models_openai` | Shared OpenAI-compatible request/response models |
| `asksachi_sdk.agents.registry` | In-process agent registry |
| `asksachi_sdk.samples.echo_agent` | Reference implementation — all three surfaces from one `WorkflowSpec` |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Install

```bash
# As a dependency in another project
pip install asksachi-sdk

# For development / running tests
git clone https://github.com/skarkala-akm/asksachi-sdk
cd asksachi-sdk
uv sync --extra dev
```

## Run the sample echo agent

The bundled echo agent shows all three surfaces from a single `WorkflowSpec`.

**CLI**:

```bash
uv run echo-agent -m "hello"
```

**A2A HTTP server** (port 8766):

```bash
uv run echo-agent-serve
```

**Smoke-test the A2A server** (once it's running):

```bash
curl http://127.0.0.1:8766/.well-known/agent-card.json
curl -X POST http://127.0.0.1:8766/message:send \
     -H "Content-Type: application/json" \
     -d '{"message": {"parts": [{"text": "hello"}]}}'
```

## Tests

```bash
uv run pytest
```

## Build your own workflow agent

```python
from asksachi_sdk.workflow_kit import workflow

spec = workflow(
    id="my-workflow",
    title="My Workflow",
    description="Does something useful.",
    version="0.1.0",
    port=8767,
)

@spec.runtime
def run(user_text: str) -> str:
    return f"You said: {user_text}"

# A2A HTTP server
app = spec.build_app()   # FastAPI app — use with TestClient or mount elsewhere
spec.serve_main()        # blocking uvicorn (call from __main__)

# CLI
spec.cli_main()          # parses -m / --message from sys.argv
```

See [`src/asksachi_sdk/samples/echo_agent/`](src/asksachi_sdk/samples/echo_agent/) for a complete working example.
