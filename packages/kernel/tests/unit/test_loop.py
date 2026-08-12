"""ReAct 循环的单元测试。用假模型客户端驱动，不需要真实 API key。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from loopbase import (
    Goal,
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

    result = loop.run(Goal(objective="东京天气怎么样？"))

    assert result.final_answer == "东京 26°C，晴天。"
    assert result.turns == 2
    assert result.stopped_by == "model"
    assert result.tool_calls_executed == ["get_weather"]
    assert result.goal.objective == "东京天气怎么样？"

    # 工具结果确实回填给了模型（第二轮上下文里有 tool 消息）
    _, tools_sent = client.calls[0]
    assert [t.name for t in tools_sent] == ["get_weather"]
    second_context = client.calls[1][0]
    assert any(m.role == "tool" and m.tool_call_id == "call_1" for m in second_context)


def test_loop_rejects_unstructured_string_input() -> None:
    client = make_client(first_tool=False)
    loop = ReActLoop(client=client, tools=make_registry())

    with pytest.raises(TypeError, match="goal must be a Goal"):
        loop.run("东京天气怎么样？")  # type: ignore[arg-type]


def test_loop_accepts_structured_goal_and_preserves_it_as_data(tmp_path) -> None:
    client = make_client(first_tool=False)
    goal = Goal(
        objective="给出东京天气建议",
        success_criteria=["包含温度", "给出出行建议"],
        constraints=["使用工具返回的数据"],
        context={"city": "东京"},
        id="goal_tokyo",
        created_at=123.0,
    )
    log = JsonlEvidenceLog(tmp_path / "evidence.jsonl")
    loop = ReActLoop(client=client, tools=make_registry(), evidence_log=log)

    result = loop.run(goal)

    assert result.goal == goal
    first_context = client.calls[0][0]
    user_message = next(message for message in first_context if message.role == "user")
    assert '"objective": "给出东京天气建议"' in user_message.content
    assert '"success_criteria"' in user_message.content

    records = log.read_all()
    goal_record = next(record for record in records if record.kind == "goal.start")
    assert goal_record.payload["goal"] == goal.as_dict()


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

    result = loop.run(Goal(objective="测试"))

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

    result = loop.run(Goal(objective="一直调用吧"))

    assert result.final_answer is None
    assert result.turns == 3
    assert result.stopped_by == "max_turns"


def test_evidence_log_records_every_transition(tmp_path) -> None:
    client = make_client()
    log_path = tmp_path / "evidence.jsonl"
    log = JsonlEvidenceLog(log_path)
    loop = ReActLoop(client=client, tools=make_registry(), evidence_log=log)

    loop.run(Goal(objective="东京天气怎么样？"))

    records = log.read_all()
    kinds = [r.kind for r in records]
    assert "turn.start" in kinds
    assert "model.response" in kinds
    assert "tool.call" in kinds
    assert "tool.result" in kinds
    assert "turn.final" in kinds
    # 每条记录都带 schema 版本
    assert all(r.schema_version == "event/v1" for r in records)


def test_every_event_carries_run_identity(tmp_path) -> None:
    """一次运行写出的所有事件共享 run_id，并标明是哪个组件写的。"""
    log = JsonlEvidenceLog(tmp_path / "evidence.jsonl", run_id="run_fixed")
    loop = ReActLoop(client=make_client(), tools=make_registry(), evidence_log=log)

    loop.run(Goal(objective="东京天气怎么样？"))

    records = log.read_all()
    assert records
    assert all(record.run_id == "run_fixed" for record in records)
    assert all(record.actor == "loop" for record in records)


def test_two_runs_share_one_file_but_not_one_run_id(tmp_path) -> None:
    """一个日志文件可以装多次运行，靠 run_id 区分。"""
    path = tmp_path / "evidence.jsonl"
    for _ in range(2):
        loop = ReActLoop(
            client=make_client(),
            tools=make_registry(),
            evidence_log=JsonlEvidenceLog(path),
        )
        loop.run(Goal(objective="东京天气怎么样？"))

    run_ids = {record.run_id for record in JsonlEvidenceLog(path).read_all()}
    assert len(run_ids) == 2


def test_causal_chain_links_tool_result_back_to_the_goal(tmp_path) -> None:
    """只看日志就能把 tool.result 一路追回 goal.start，不需要读代码。"""
    log = JsonlEvidenceLog(tmp_path / "evidence.jsonl")
    loop = ReActLoop(client=make_client(), tools=make_registry(), evidence_log=log)

    loop.run(Goal(objective="东京天气怎么样？"))

    records = log.read_all()
    by_id = {record.id: record for record in records}
    goal_start = next(r for r in records if r.kind == "goal.start")
    assert goal_start.caused_by is None  # 根事件

    cursor = next(r for r in records if r.kind == "tool.result")
    chain = [cursor.kind]
    while cursor.caused_by is not None:
        cursor = by_id[cursor.caused_by]
        chain.append(cursor.kind)

    assert chain == [
        "tool.result",
        "tool.call",
        "model.response",
        "turn.start",
        "goal.start",
    ]


def test_read_all_marks_pre_identity_rows_as_unknown(tmp_path) -> None:
    """加身份字段之前写下的旧日志仍然能读，缺的字段标 unknown 而不是编造。"""
    path = tmp_path / "old.jsonl"
    path.write_text(
        '{"kind": "turn.start", "payload": {"turn": 1}, "timestamp": 1.0,'
        ' "id": "abc", "schema_version": "event/v1"}\n',
        encoding="utf-8",
    )

    (record,) = JsonlEvidenceLog(path).read_all()

    assert record.kind == "turn.start"
    assert record.run_id == "unknown"
    assert record.actor == "unknown"
    assert record.caused_by is None
