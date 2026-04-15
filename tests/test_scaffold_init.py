from __future__ import annotations

from pathlib import Path

import pytest

from asksachi_sdk.scaffold.init import generate_skeleton, ScaffoldConfig


def test_generate_skeleton_writes_expected_files(tmp_path: Path) -> None:
    target = tmp_path / "my-agent"
    cfg = ScaffoldConfig(
        project_dir=target,
        workflow_id="my-agent",
        title="My Agent",
        description="A simple agent.",
        package="my_agent",
        port=8766,
    )
    generate_skeleton(cfg)

    assert (target / "pyproject.toml").exists()
    assert (target / "README.md").exists()
    assert (target / "src" / "my_agent" / "agent.py").exists()
    assert (target / "tests" / "test_smoke.py").exists()
    assert (target / "skills" / "asksachi-contract-guard" / "SKILL.md").exists()

    pyproject = (target / "pyproject.toml").read_text(encoding="utf-8")
    assert "asksachi-sdk @ file://" in pyproject  # local checkout should be detected in SDK test runs
    assert "allow-direct-references = true" in pyproject

    agent_py = (target / "src" / "my_agent" / "agent.py").read_text(encoding="utf-8")
    assert 'id="my-agent"' in agent_py
    assert "app = spec.build_app()" in agent_py
    assert "serve_main = spec.serve_main" in agent_py
    assert "cli_main = spec.cli_main" in agent_py


def test_generate_skeleton_refuses_nonempty_dir_without_force(tmp_path: Path) -> None:
    target = tmp_path / "agent"
    target.mkdir()
    (target / "existing.txt").write_text("x", encoding="utf-8")
    cfg = ScaffoldConfig(
        project_dir=target,
        workflow_id="agent",
        title="Agent",
        description="d",
        package="agent",
        port=8766,
    )
    with pytest.raises(SystemExit, match="not empty"):
        generate_skeleton(cfg, force=False)

