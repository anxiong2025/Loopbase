"""Layer 1 — 核心循环控制。

一个最小但完整的 ReAct 循环：
    user 消息 → 模型（带工具定义）→ 若 finish_reason=tool_calls 则执行工具、
    结果回填 → 再调模型 → 直到 finish_reason=stop 或达到最大轮数。

循环不关心模型是谁（ModelClient）、工具是什么（ToolRegistry）——
这两个都是构造参数，这就是 Stage 1「循环通用化」的完成标准。
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .goals import Goal
from .models.base import Message, ModelClient
from .observability import Actor, EventKind
from .state import EvidenceLog
from .tools.registry import ToolRegistry


@dataclass
class RunResult:
    final_answer: str | None
    turns: int
    goal: Goal
    messages: list[Message] = field(default_factory=list)
    tool_calls_executed: list[str] = field(default_factory=list)
    stopped_by: str = ""  # "model" | "max_turns"


class ReActLoop:
    def __init__(
        self,
        *,
        client: ModelClient,
        tools: ToolRegistry,
        max_turns: int = 8,
        system_prompt: str = "",
        evidence_log: EvidenceLog | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self.evidence_log = evidence_log
        self.on_event = on_event

    def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
        """Execute a structured Stage 2 goal.

        ``caused_by`` lets a caller (e.g. ``TaskExecutor``) hang this run under the
        event that delegated it, so the causal chain survives across components.
        """
        if not isinstance(goal, Goal):
            raise TypeError("goal must be a Goal")

        messages: list[Message] = []
        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))
        messages.append(Message(role="user", content=goal.to_user_message()))

        goal_event = self._log(
            EventKind.GOAL_START, {"goal": goal.as_dict()}, caused_by=caused_by
        )

        executed: list[str] = []
        stopped_by = ""

        for turn in range(1, self.max_turns + 1):
            turn_event = self._log(
                EventKind.TURN_START,
                {"turn": turn, "message_count": len(messages)},
                caused_by=goal_event,
            )

            response = self.client.complete(messages, self.tools.specs())
            messages.append(response.message)
            model_event = self._log(
                EventKind.MODEL_RESPONSE,
                {
                    "turn": turn,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                    "content": response.message.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in (response.message.tool_calls or [])
                    ],
                },
                caused_by=turn_event,
            )

            if response.finish_reason == "tool_calls" and response.message.tool_calls:
                for call in response.message.tool_calls:
                    result_text = self._execute_tool(
                        call.name, call.arguments, turn, caused_by=model_event
                    )
                    executed.append(call.name)
                    messages.append(
                        Message(
                            role="tool",
                            content=result_text,
                            tool_call_id=call.id,
                        )
                    )
                continue

            # finish_reason = stop：模型给出了最终回答
            stopped_by = "model"
            self._log(
                EventKind.TURN_FINAL,
                {"turn": turn, "answer": response.message.content},
                caused_by=model_event,
            )
            return RunResult(
                final_answer=response.message.content,
                turns=turn,
                messages=messages,
                tool_calls_executed=executed,
                stopped_by=stopped_by,
                goal=goal,
            )

        stopped_by = "max_turns"
        self._log(
            EventKind.TURN_MAX_TURNS, {"turns": self.max_turns}, caused_by=goal_event
        )
        return RunResult(
            final_answer=None,
            turns=self.max_turns,
            messages=messages,
            tool_calls_executed=executed,
            stopped_by=stopped_by,
            goal=goal,
        )

    def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        turn: int,
        *,
        caused_by: str | None = None,
    ) -> str:
        """执行单个工具调用。报错也回填给模型，不让循环 crash。"""
        call_event = self._log(
            EventKind.TOOL_CALL,
            {"turn": turn, "name": name, "arguments": arguments},
            caused_by=caused_by,
        )
        try:
            result = self.tools.execute(name, arguments)
        except Exception as exc:  # noqa: BLE001 — 任何错误都回填，让模型自己纠正
            message = f"工具 {name} 执行失败: {exc}\n{traceback.format_exc(limit=2)}"
            self._log(
                EventKind.TOOL_ERROR,
                {"turn": turn, "name": name, "error": str(exc)},
                caused_by=call_event,
            )
            return message
        self._log(
            EventKind.TOOL_RESULT,
            {"turn": turn, "name": name, "result": result},
            caused_by=call_event,
        )
        return result

    def _log(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        caused_by: str | None = None,
    ) -> str | None:
        """写一条证据，返回它的事件 id 供下游事件挂 caused_by。

        没接证据日志时返回 None，因果链自然退化成全 None——on_event 的
        订阅者（比如 API 的 SSE 流）签名不受影响。
        """
        event_id: str | None = None
        if self.evidence_log is not None:
            event_id = self.evidence_log.append(
                kind, payload, actor=Actor.LOOP, caused_by=caused_by
            ).id
        if self.on_event is not None:
            self.on_event(str(kind), payload)
        return event_id
