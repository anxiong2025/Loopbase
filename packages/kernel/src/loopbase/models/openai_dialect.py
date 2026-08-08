"""Layer 2 — OpenAI / DeepSeek 方言的 ModelClient 实现。

只依赖标准库（urllib），保持内核零强制运行时依赖。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import Message, ModelClient, ModelResponse, ToolCall, ToolSpec


class OpenAICompatibleClient(ModelClient):
    """兼容 OpenAI / DeepSeek 的 chat/completions 方言。

    关键方言差异（与 Anthropic 相对）：
    - finish_reason="tool_calls" 表示模型想调工具，需要继续循环
    - tool call 的 arguments 是 JSON 字符串，需要二次解析
    - 工具结果回填 role="tool"，必须带 tool_call_id
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
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
        body = {
            "model": self.model,
            "messages": [_encode_message(m) for m in messages],
            "tools": [
                {
                    "type": "function",
                    "function": spec.as_dict(),
                }
                for spec in tools
            ],
        }
        data = self._post("/chat/completions", body)
        choice = data["choices"][0]
        raw_msg = choice["message"]

        tool_calls: list[ToolCall] | None = None
        if raw_msg.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
                for tc in raw_msg["tool_calls"]
            ]

        return ModelResponse(
            message=Message(
                role="assistant",
                content=raw_msg.get("content") or "",
                tool_calls=tool_calls,
            ),
            finish_reason=choice.get("finish_reason") or "stop",
            usage=data.get("usage"),
            raw=data,
        )

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
    base: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.role == "tool":
        base["tool_call_id"] = message.tool_call_id
    elif message.role == "assistant" and message.tool_calls:
        base["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in message.tool_calls
        ]
    return base
