"""ReAct 循环的单元测试。用假模型客户端驱动，不需要真实 API key。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from loopbase import (
    JsonlEvidenceLog,
    Message,
    ModelResponse,
    ReActLoop,
    ToolCall,
    ToolRegistry,
)


@dataclass
class ScriptedClient:
    """按脚本顺序返回响应。last_messages 记录每次收到的完整上下文。"""

    script: list[ModelResponse]
    calls: list[tuple[list[Message], list]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        response = self.script.pop(0)
        return response


def make_client(
    *,
    first_tool: bool = True,
    final_content: str = "东京 26°C，晴天。",
) -> ScriptedClient:
    script: list[ModelResponse] = []
    if first_tool:
        script.append(
            ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(id="call_1", name="get_weather", arguments={"city": "东京"})
                    ],
                ),
                finish_reason="tool_calls",
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            )
        )
    script.append(
        ModelResponse(
            message=Message(role="assistant", content=final_content),
            finish_reason="stop",
        )
    )
    return ScriptedClient(script=script)


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()

    def get_weather(city: str) -> str:
        fake_db = {"东京": "26°C 晴，湿度 60%", "北京": "32°C 晴"}
        return fake_db.get(city, f"暂无 {city} 的天气数据")

    registry.register(
        name="get_weather",
        description="查询指定城市的实时天气",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如：东京"},
            },
            "required": ["city"],
        },
        impl=get_weather,
    )
    return registry


def test_loop_runs_tool_then_answers() -> None:
    client = make_client()
    loop = ReActLoop(client=client, tools=make_registry())

    result = loop.run("东京天气怎么样？")

    assert result.final_answer == "东京 26°C，晴天。"
    assert result.turns == 2
    assert result.stopped_by == "model"
    assert result.tool_calls_executed == ["get_weather"]

    # 工具结果确实回填给了模型（第二轮上下文里有 tool 消息）
    _, tools_sent = client.calls[0]
    assert [t.name for t in tools_sent] == ["get_weather"]
    second_context = client.calls[1][0]
    assert any(m.role == "tool" and m.tool_call_id == "call_1" for m in second_context)


def test_registry_rejects_duplicate_name() -> None:
    registry = make_registry()
    with pytest.raises(ValueError, match="工具已存在"):
        registry.register(
            name="get_weather",
            description="x",
            parameters={},
            impl=lambda: "x",
        )


def test_unknown_tool_returns_error_instead_of_crashing() -> None:
    client = make_client(first_tool=True)
    registry = make_registry()
    # 让模型调用一个不存在的工具
    client.script.insert(
        0,
        ModelResponse(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(id="call_x", name="no_such_tool", arguments={})
                ],
            ),
            finish_reason="tool_calls",
        ),
    )
    loop = ReActLoop(client=client, tools=registry)

    result = loop.run("测试")

    assert result.final_answer is not None
    # 错误作为 tool 结果回填，模型看到了错误文本
    second_context = client.calls[-1][0]
    tool_msg = next(m for m in second_context if m.role == "tool")
    assert "执行失败" in tool_msg.content


def test_loop_stops_at_max_turns() -> None:
    tool_response = ModelResponse(
        message=Message(
            role="assistant",
            tool_calls=[ToolCall(id="c", name="get_weather", arguments={"city": "东京"})],
        ),
        finish_reason="tool_calls",
    )
    client = ScriptedClient(script=[tool_response] * 10)  # 永远想调工具
    loop = ReActLoop(client=client, tools=make_registry(), max_turns=3)

    result = loop.run("一直调用吧")

    assert result.final_answer is None
    assert result.turns == 3
    assert result.stopped_by == "max_turns"


def test_evidence_log_records_every_transition(tmp_path) -> None:
    client = make_client()
    log_path = tmp_path / "evidence.jsonl"
    log = JsonlEvidenceLog(log_path)
    loop = ReActLoop(client=client, tools=make_registry(), evidence_log=log)

    loop.run("东京天气怎么样？")

    records = log.read_all()
    kinds = [r.kind for r in records]
    assert "turn.start" in kinds
    assert "model.response" in kinds
    assert "tool.call" in kinds
    assert "tool.result" in kinds
    assert "turn.final" in kinds
    # 每条记录都带 schema 版本
    assert all(r.schema_version == "event/v1" for r in records)
