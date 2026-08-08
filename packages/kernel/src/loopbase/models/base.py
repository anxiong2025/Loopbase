"""Layer 2 — 模型 I/O 的统一表示与 ModelClient 协议。

设计原则：循环核心只依赖这里的统一类型，不直接碰任何厂商的
请求/响应方言。新增模型后端 = 实现 ModelClient 协议，循环代码不动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolSpec:
    """工具定义（JSON Schema 形式），发给模型用。"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class ToolCall:
    """模型发出的调用意图。arguments 已解析为对象（方言差异在客户端内消化）。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """统一消息表示。

    - role: system / user / assistant / tool
    - tool_calls: 仅 assistant 消息携带
    - tool_call_id: 仅 tool 消息携带，用于配对
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class ModelResponse:
    """统一模型响应。finish_reason 归一化为 tool_calls / stop。"""

    message: Message
    finish_reason: str
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ModelClient(Protocol):
    """所有模型后端的统一契约。实现方负责方言转换与网络错误归一化。"""

    def complete(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> ModelResponse: ...
