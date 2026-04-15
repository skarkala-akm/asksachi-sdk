## AskSachi SDK Contract Guard

### Purpose
Keep **external contracts stable** when editing `asksachi-sdk`. This SDK is used by other projects and tools that expect
specific HTTP endpoints, payload shapes, and streaming behavior.

### Also required (agent repos)
If you are building an agent repo that depends on `asksachi-sdk`, include this skill file in that agent repo too (for
example at `skills/asksachi-contract-guard/SKILL.md`) so coding agents don’t accidentally break external contracts.

### What must NOT break (compatibility rules)

- **A2A HTTP surface**
  - `GET /.well-known/agent-card.json` must keep working
  - `POST /message:send` must keep working
  - Response for `POST /message:send` must include a completed `task` object with:
    - `task.status.state == "TASK_STATE_COMPLETED"`
    - `task.artifacts[0].parts[0].mediaType == "text/plain"`
    - `task.artifacts[0].parts[0].text` containing the reply

- **Streaming behavior**
  - If request header includes `Accept: application/x-ndjson`, response must stream:
    - one or more `{ "type": "delta", "text": "..." }` lines
    - one final `{ "type": "complete", "task": { ... } }` line

- **Agent Card JSON**
  - Must keep returning JSON with `skills` and the expected top-level fields (`name`, `description`, `version`, etc.)

- **Workflow author API**
  - `WorkflowSpec` / `workflow()` must continue to produce:
    - `spec.build_app()` (FastAPI app)
    - `spec.serve_main()` (uvicorn entrypoint)
    - `spec.cli_main()` (CLI entrypoint)
    - `spec.agent` (AskSachi chat surface adapter)

### Required verification before finishing a change

If you change **agent code** (anything under `src/asksachi_sdk/` that affects behavior or contracts), you must:
- **add or update tests** that cover the change (new behavior, bug fix, or edge case)
- run the full test suite and ensure it passes

Run the SDK tests **in the SDK repo**:

```bash
uv sync --extra dev
uv run pytest
```

These tests are the contract:
- `tests/test_sdk_a2a.py` (endpoints, payload shape, NDJSON streaming)
- `tests/test_sdk_workflow_kit.py` (WorkflowSpec + chat/CLI surfaces)

### When a change is allowed to be breaking
Only introduce a breaking change if you also:
- bump the major version, and
- clearly document the breaking change in `README.md`

