"""Tests for model-proposed, runtime-owned task planning."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from loopbase import (
    Goal,
    Message,
    ModelResponse,
    PlanGenerationError,
    TaskPlanner,
    TaskStatus,
)


@dataclass
class PlannerClient:
    content: str
    calls: list[tuple[list[Message], list]] = field(default_factory=list)

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        return ModelResponse(
            message=Message(role="assistant", content=self.content),
            finish_reason="stop",
        )


def _goal() -> Goal:
    return Goal(
        id="goal_trip",
        objective="制定从深圳出发的北京三日游计划",
        success_criteria=("给出每日行程", "总费用不超过预算"),
        constraints=("预算不超过 3000 元",),
        context={"origin": "深圳", "destination": "北京", "days": 3},
        created_at=1.0,
    )


def _proposal() -> dict:
    return {
        "tasks": [
            {
                "key": "research",
                "title": "查询交通和景点",
                "description": "收集交通、住宿、景点价格和开放时间",
                "depends_on": [],
                "completion_criteria": ["关键价格和时间均有来源"],
            },
            {
                "key": "itinerary",
                "title": "编排三日行程",
                "description": "结合位置和时间生成每日路线",
                "depends_on": ["research"],
                "completion_criteria": ["三天均有明确安排"],
            },
            {
                "key": "validate",
                "title": "核验预算和约束",
                "description": "检查总费用和所有成功标准",
                "depends_on": ["itinerary"],
                "completion_criteria": ["总费用不超过 3000 元"],
            },
        ]
    }


def test_planner_turns_model_keys_into_runtime_owned_task_ids() -> None:
    client = PlannerClient(json.dumps(_proposal(), ensure_ascii=False))
    plan = TaskPlanner(client=client).plan(_goal())

    assert plan.goal_id == "goal_trip"
    assert [task.status for task in plan.tasks] == [TaskStatus.PENDING] * 3
    assert plan.tasks[0].id != "research"
    assert plan.tasks[1].depends_on == (plan.tasks[0].id,)
    assert plan.tasks[2].depends_on == (plan.tasks[1].id,)
    assert client.calls[0][1] == []
    assert "必须使用简体中文" in client.calls[0][0][-1].content


def test_planner_can_return_the_unprocessed_model_response() -> None:
    content = json.dumps(_proposal(), ensure_ascii=False)
    client = PlannerClient(content)

    result = TaskPlanner(client=client).plan_with_trace(_goal())

    assert result.raw_model_content == content
    assert result.finish_reason == "stop"
    assert result.provider_response == {}
    assert result.plan.tasks[0].title == "查询交通和景点"


def test_planner_accepts_a_json_code_fence() -> None:
    content = "```json\n" + json.dumps(_proposal(), ensure_ascii=False) + "\n```"

    plan = TaskPlanner(client=PlannerClient(content)).plan(_goal())

    assert len(plan.tasks) == 3


def test_planner_rejects_unknown_dependencies() -> None:
    proposal = _proposal()
    proposal["tasks"][1]["depends_on"] = ["missing"]

    with pytest.raises(PlanGenerationError, match="unknown dependencies"):
        TaskPlanner(client=PlannerClient(json.dumps(proposal))).plan(_goal())


def test_planner_rejects_cyclic_dependencies() -> None:
    proposal = _proposal()
    proposal["tasks"][0]["depends_on"] = ["validate"]

    with pytest.raises(PlanGenerationError, match="cycle"):
        TaskPlanner(client=PlannerClient(json.dumps(proposal))).plan(_goal())


def test_planner_rejects_self_dependencies() -> None:
    proposal = _proposal()
    proposal["tasks"][0]["depends_on"] = ["research"]

    with pytest.raises(PlanGenerationError, match="cannot depend on itself"):
        TaskPlanner(client=PlannerClient(json.dumps(proposal))).plan(_goal())


def test_planner_rejects_invalid_json() -> None:
    with pytest.raises(PlanGenerationError, match="invalid JSON"):
        TaskPlanner(client=PlannerClient("not json")).plan(_goal())
