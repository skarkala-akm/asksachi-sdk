"""AskSachi **chat** surface for text-in / text-out workflows (OpenAI-shaped responses).

The ``reply`` callable passed to :class:`SimpleTextWorkflowAgent` can be:

- ``def run(text: str) -> str``                     — sync, returns full reply
- ``async def run(text: str) -> str``               — async, returns full reply
- ``def run(text: str) -> Iterable[str]``           — sync generator / iterable of chunks
- ``async def run(text: str) -> AsyncIterable[str]``— async generator of chunks
"""

from __future__ import annotations

import inspect
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from asksachi_sdk.models_openai import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompletionUsage,
    stream_chunk_dict,
)


def last_user_text(req: ChatCompletionRequest) -> str:
    """Last ``user`` message ``content`` in the chat completion request (or empty string)."""
    for m in reversed(req.messages):
        if m.role == "user" and m.content:
            return str(m.content)
    return ""


async def _get_reply_text(fn: Callable[..., Any], user_text: str) -> str:
    """Call runtime and return the full reply as a string (sync, async, or iterable)."""
    result = fn(user_text)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, str):
        return result
    chunks: list[str] = []
    if hasattr(result, "__aiter__"):
        async for chunk in result:
            chunks.append(str(chunk))
    else:
        for chunk in result:
            chunks.append(str(chunk))
    return "".join(chunks)


async def _iter_reply_chunks(fn: Callable[..., Any], user_text: str) -> AsyncIterator[str]:
    """Normalise any runtime return type into an async stream of string chunks for SSE."""
    text = await _get_reply_text(fn, user_text)
    for line in text.split("\n"):
        yield line + "\n"


class SimpleTextWorkflowAgent:
    """Minimal agent: maps last user text → reply via ``reply``.

    ``reply`` may be sync or async, and may return a full string or yield chunks —
    all four combinations are handled transparently.
    """

    def __init__(
        self,
        *,
        workflow_id: str,
        title: str,
        description: str,
        version: str,
        execution_mode: str = "single",
        reply: Callable[..., Any],
    ) -> None:
        self.id = workflow_id
        self.title = title
        self.description = description
        self.version = version
        self.execution_mode = execution_mode
        self._reply = reply

    async def _get_reply_text(self, req: ChatCompletionRequest) -> str:
        return await _get_reply_text(self._reply, last_user_text(req))

    async def complete_chat(self, req: ChatCompletionRequest) -> dict[str, Any]:
        created = int(time.time())
        cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        text = await self._get_reply_text(req)
        return ChatCompletionResponse(
            id=cid,
            created=created,
            model=req.model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=text),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=0,
                completion_tokens=max(1, len(text) // 4),
                total_tokens=max(1, len(text) // 4),
            ),
        ).model_dump()

    async def stream_chat(self, req: ChatCompletionRequest) -> AsyncIterator[str]:
        created = int(time.time())
        cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        yield f"data: {json.dumps(stream_chunk_dict(completion_id=cid, model=req.model, created=created, content_delta=''))}\n\n"
        async for delta in _iter_reply_chunks(self._reply, last_user_text(req)):
            yield f"data: {json.dumps(stream_chunk_dict(completion_id=cid, model=req.model, created=created, content_delta=delta))}\n\n"
        yield f"data: {json.dumps(stream_chunk_dict(completion_id=cid, model=req.model, created=created, content_delta=None, finish_reason='stop'))}\n\n"
        yield "data: [DONE]\n\n"
