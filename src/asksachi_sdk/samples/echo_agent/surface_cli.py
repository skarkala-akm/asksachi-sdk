"""CLI surface for test-echo (shim — logic lives in echo_agent.py)."""

from .echo_agent import spec

main = spec.cli_main
