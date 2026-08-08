"""Layer 2 — Anthropic 方言的 ModelClient 实现。

关键方言差异（与 OpenAI/DeepSeek 相对）：
- system 消息是请求体顶层的独立字段，不是 messages 里的一条
- stop_reason="tool_use" 表示模型想调工具
- tool_use 的 input 直接是对象，不需要二次解析
- 工具结果回填 role="user" 的 tool_result block，配对字段是 tool_use_id
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import Message, ModelClient, ModelResponse, ToolCall, ToolSpec


class AnthropicClient(ModelClient):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        model: str = "claude-sonnet-4-5",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> ModelResponse:
        system_parts = [
            m.content for m in messages if m.role == "system" and m.content
        ]
        conversation = [
            _encode_message(m)
            for m in messages
            if m.role in ("user", "assistant", "tool")
        ]
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conversation,
            "tools": [spec.as_dict() for spec in tools],
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)

        data = self._post("/messages", body)
        tool_calls: list[ToolCall] | None = None
        text_parts: list[str] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input") or {},
                    )
                )

        stop_reason = data.get("stop_reason") or "end_turn"
        return ModelResponse(
            message=Message(
                role="assistant",
                content="".join(text_parts),
                tool_calls=tool_calls,
            ),
            finish_reason="tool_calls" if stop_reason == "tool_use" else "stop",
            usage=data.get("usage"),
            raw=data,
        )

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"HTTP {exc.code}: {exc.read().decode()[:500]}"
            ) from exc


def _encode_message(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            ],
        }
    if message.role == "assistant" and message.tool_calls:
        blocks: list[dict[str, Any]] = []
        if message.content:
            blocks.append({"type": "text", "text": message.content})
        for tc in message.tool_calls:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )
        return {"role": "assistant", "content": blocks}
    return {"role": message.role, "content": message.content}
