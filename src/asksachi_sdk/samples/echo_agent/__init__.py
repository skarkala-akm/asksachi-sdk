"""Reference workflow ``test-echo``: one file, all surfaces via ``WorkflowSpec``."""

from .echo_agent import (
    WORKFLOW_WELCOME_TRIGGER,
    run,
    spec,
)

__all__ = ["WORKFLOW_WELCOME_TRIGGER", "run", "spec"]
