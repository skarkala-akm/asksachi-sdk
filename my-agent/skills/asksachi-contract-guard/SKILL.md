## AskSachi SDK Contract Guard

### Purpose
Keep **external contracts stable** when editing this agent repo. Other tools expect specific HTTP endpoints, payload
shapes, and streaming behavior.

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

### Required verification before finishing a change

If you change agent behavior or contracts, you must:
- **add or update tests** that cover the change
- run the full test suite and ensure it passes

```bash
uv sync --extra dev
uv run pytest
```
