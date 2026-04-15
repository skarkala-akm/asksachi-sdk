"""Generate a minimal AskSachi-compatible agent skeleton project.

This intentionally avoids external templating dependencies so the SDK stays lightweight.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


_CONTRACT_GUARD_SKILL_MD = """## AskSachi SDK Contract Guard

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
"""


def _local_asksachi_sdk_dependency() -> str | None:
    """Return a PEP 508 direct URL dependency for a local asksachi-sdk checkout, if detectable."""
    # When running `asksachi-init` from a source checkout, __file__ points into:
    #   <repo>/src/asksachi_sdk/scaffold/init.py
    # so parents[3] should be the repo root.
    sdk_root = Path(__file__).resolve().parents[3]
    pyproject = sdk_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    txt = pyproject.read_text(encoding="utf-8")
    if 'name = "asksachi-sdk"' not in txt:
        return None
    return f"asksachi-sdk @ {sdk_root.as_uri()}"


def _default_asksachi_sdk_dependency() -> str:
    """Dependency string for generated agent projects.

    - Prefer local file:// when running from a source checkout (fast iteration).
    - Fall back to a git URL so a fresh machine can install without a local checkout.
    """
    return _local_asksachi_sdk_dependency() or "asksachi-sdk @ git+https://github.com/skarkala-akm/asksachi-sdk"


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "my-agent"


def _py_package_name(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_{2,}", "_", s).strip("_")
    if not s:
        s = "my_agent"
    if s[0].isdigit():
        s = f"agent_{s}"
    return s


@dataclass(frozen=True)
class ScaffoldConfig:
    project_dir: Path
    workflow_id: str
    title: str
    description: str
    package: str
    port: int


def _render_pyproject(cfg: ScaffoldConfig) -> str:
    cli_script = f"{_slugify(cfg.workflow_id)}-cli"
    serve_script = f"{_slugify(cfg.workflow_id)}-serve"
    mod = f"{cfg.package}.agent"
    dep = _default_asksachi_sdk_dependency()
    allow_direct = " @ " in dep
    out = (
        '[project]\n'
        f'name = "{_slugify(cfg.workflow_id)}"\n'
        'version = "0.1.0"\n'
        f'description = "{cfg.description}"\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.12"\n'
        "dependencies = [\n"
        f'    "{dep}",\n'
        "]\n"
        "\n"
        "[project.scripts]\n"
        f'{cli_script} = "{mod}:cli_main"\n'
        f'{serve_script} = "{mod}:serve_main"\n'
        "\n"
    )
    if allow_direct:
        out += "[tool.hatch.metadata]\nallow-direct-references = true\n\n"
    out += (
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
        "\n"
        "[tool.hatch.build.targets.wheel]\n"
        'packages = ["src/' + cfg.package + '"]\n'
    )
    return out


def _render_agent_py(cfg: ScaffoldConfig) -> str:
    return (
        "from __future__ import annotations\n\n"
        "from asksachi_sdk.workflow_kit import workflow\n\n"
        "spec = workflow(\n"
        f'    id="{cfg.workflow_id}",\n'
        f'    title="{cfg.title}",\n'
        f'    description="{cfg.description}",\n'
        '    version="0.1.0",\n'
        f"    port={cfg.port},\n"
        ")\n\n\n"
        "@spec.runtime\n"
        "def run(user_text: str) -> str:\n"
        '    return f"You said: {user_text}"\n\n\n'
        "# Expose common surfaces\n"
        "app = spec.build_app()  # FastAPI app (use with TestClient)\n"
        "serve_main = spec.serve_main\n"
        "cli_main = spec.cli_main\n"
    )


def _render_readme(cfg: ScaffoldConfig) -> str:
    cli_script = f"{_slugify(cfg.workflow_id)}-cli"
    serve_script = f"{_slugify(cfg.workflow_id)}-serve"
    return (
        f"# {cfg.title}\n\n"
        f"{cfg.description}\n\n"
        "## How it works (flow)\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        '  U["User"] --> M["Your runtime function\\n(user text → reply text)"]\n'
        '  M --> C["CLI (' + cli_script + ')"]\n'
        '  M --> H["HTTP server (' + serve_script + ')"]\n'
        "```\n\n"
        "## Run (CLI)\n\n"
        "```bash\n"
        f'uv run {cli_script} -m "hello"\n'
        "```\n\n"
        "## Install notes\n\n"
        "This project depends on `asksachi-sdk`. On a fresh machine, `uv sync` will fetch it from Git.\n\n"
        "## Run (HTTP server)\n\n"
        "```bash\n"
        f"uv run {serve_script}\n"
        "```\n\n"
        "## Smoke test (once the server is running)\n\n"
        "```bash\n"
        f"curl http://127.0.0.1:{cfg.port}/.well-known/agent-card.json\n"
        f"curl -X POST http://127.0.0.1:{cfg.port}/message:send \\\n"
        '     -H "Content-Type: application/json" \\\n'
        '     -d \'{"message": {"parts": [{"text": "hello"}]}}\'\n'
        "```\n"
    )


def _render_test(cfg: ScaffoldConfig) -> str:
    return (
        "from __future__ import annotations\n\n"
        "from fastapi.testclient import TestClient\n\n"
        f"from {cfg.package}.agent import app\n\n\n"
        "def test_agent_card_and_message_send() -> None:\n"
        "    c = TestClient(app)\n"
        "    r = c.get('/.well-known/agent-card.json')\n"
        "    assert r.status_code == 200\n"
        "    r2 = c.post('/message:send', json={'message': {'parts': [{'text': 'ping'}]}})\n"
        "    assert r2.status_code == 200\n"
        "    assert r2.json()['task']['status']['state'] == 'TASK_STATE_COMPLETED'\n"
    )


def generate_skeleton(cfg: ScaffoldConfig, *, force: bool = False) -> None:
    root = cfg.project_dir
    if root.exists():
        if not root.is_dir():
            raise SystemExit(f"target exists and is not a directory: {root}")
        if any(root.iterdir()) and not force:
            raise SystemExit(f"target directory is not empty: {root} (use --force)")
    root.mkdir(parents=True, exist_ok=True)

    (root / "src" / cfg.package).mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "asksachi-contract-guard").mkdir(parents=True, exist_ok=True)

    (root / "README.md").write_text(_render_readme(cfg), encoding="utf-8")
    (root / "pyproject.toml").write_text(_render_pyproject(cfg), encoding="utf-8")
    (root / "src" / cfg.package / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / cfg.package / "agent.py").write_text(_render_agent_py(cfg), encoding="utf-8")
    (root / "tests" / "test_smoke.py").write_text(_render_test(cfg), encoding="utf-8")
    (root / "skills" / "asksachi-contract-guard" / "SKILL.md").write_text(
        _CONTRACT_GUARD_SKILL_MD, encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate a minimal AskSachi-compatible agent skeleton.")
    p.add_argument("path", help="Target directory to create (e.g. my-agent)")
    p.add_argument("--id", dest="workflow_id", default="", help="Workflow id (default: derived from path)")
    p.add_argument("--title", default="", help="Agent title (default: derived from id)")
    p.add_argument("--description", default="A simple AskSachi-compatible agent.", help="Agent description")
    p.add_argument("--package", default="", help="Python package name (default: derived from id)")
    p.add_argument("--port", type=int, default=8766, help="Default HTTP port")
    p.add_argument("--force", action="store_true", help="Write into a non-empty target directory")
    ns = p.parse_args(list(argv) if argv is not None else None)

    target = Path(ns.path).expanduser().resolve()
    wid = ns.workflow_id.strip() or _slugify(target.name)
    title = ns.title.strip() or wid.replace("-", " ").title()
    pkg = ns.package.strip() or _py_package_name(wid)

    cfg = ScaffoldConfig(
        project_dir=target,
        workflow_id=wid,
        title=title,
        description=str(ns.description).strip() or "A simple AskSachi-compatible agent.",
        package=pkg,
        port=int(ns.port),
    )
    generate_skeleton(cfg, force=bool(ns.force))
    print(f"created agent skeleton in {target}")


if __name__ == "__main__":
    main(sys.argv[1:])

