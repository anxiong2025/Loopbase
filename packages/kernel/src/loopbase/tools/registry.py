"""Layer 3 — 工具注册表。

工具 = 定义（给模型看的 JSON Schema）+ 实现（我们执行的函数）。
注册表支持运行时动态注册：新工具在程序运行期间随时 register，循环不用改。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..models.base import ToolSpec


ToolImpl = Callable[..., Any]


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    impl: ToolImpl

    @property
    def name(self) -> str:
        return self.spec.name


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        impl: ToolImpl,
    ) -> RegisteredTool:
        """运行时注册一个工具。同名注册视为错误（避免静默覆盖）。"""
        if name in self._tools:
            raise ValueError(f"工具已存在: {name}")
        tool = RegisteredTool(
            spec=ToolSpec(name=name, description=description, parameters=parameters),
            impl=impl,
        )
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """执行工具并把结果归一化为字符串（回填给模型的格式）。

        返回值必须是字符串，模型只消费字符串。业务返回对象时由实现方
        自行序列化；注册表不猜格式。
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"未知工具: {name}")
        result = tool.impl(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
