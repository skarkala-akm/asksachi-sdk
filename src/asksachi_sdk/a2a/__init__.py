"""Shared Agent2Agent (A2A) protocol helpers — HTTP+JSON binding (minimal subset).

See https://a2a-protocol.org/latest/specification/

Workflow packages implement only **runtime** logic (e.g. ``user_text -> reply_text``);
this package provides discovery, ``message:send``, and completed-task payloads.
"""

from asksachi_sdk.a2a.http_json import (
    NDJSON_MEDIA_TYPE,
    AgentCardSpec,
    build_agent_card_json,
    build_completed_task_with_text_artifact,
    create_minimal_a2a_http_json_router,
    extract_user_text_from_message,
)

__all__ = [
    "NDJSON_MEDIA_TYPE",
    "AgentCardSpec",
    "build_agent_card_json",
    "build_completed_task_with_text_artifact",
    "create_minimal_a2a_http_json_router",
    "extract_user_text_from_message",
]
