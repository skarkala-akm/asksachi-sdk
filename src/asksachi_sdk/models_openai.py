"""Subset of OpenAI Chat Completions API types (request + response bodies)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "asksachi-default"
    messages: list[ChatMessage]
    temperature: float | None = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = None
    stream: bool = False
    user: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class ChatCompletionMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] | None = "stop"


class CompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: CompletionUsage


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 1700000000
    owned_by: str = "asksachi"


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]


def stream_chunk_dict(
    *,
    completion_id: str,
    model: str,
    created: int,
    content_delta: str | None,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    """One SSE JSON object compatible with OpenAI streaming."""
    choice: dict[str, Any] = {"index": 0, "delta": {}}
    if content_delta is not None:
        choice["delta"]["content"] = content_delta
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [choice],
    }
