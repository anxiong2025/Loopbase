"""HTTP boundary tests for the Stage 2 structured-goal contract."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from loopbase import Message, ModelResponse

from api import main
from api.main import AnalyzeRequest, PlanRequest, app


def test_analyze_request_builds_a_domain_goal() -> None:
    request = AnalyzeRequest.model_validate(
        {
            "goal": {
                "objective": "分析 AAPL",
                "success_criteria": ["使用真实数据"],
                "constraints": ["注明风险"],
                "context": {"ticker": "AAPL"},
            },
            "max_turns": 5,
        }
    )

    goal = request.goal.to_domain()

    assert goal.schema_version == "goal/v1"
    assert goal.objective == "分析 AAPL"
    assert goal.success_criteria == ("使用真实数据",)
    assert goal.context == {"ticker": "AAPL"}


@pytest.mark.parametrize("payload", [{}, {"question": "旧字符串入口"}])
def test_analyze_request_rejects_missing_or_legacy_goal(payload) -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(payload)


def test_plan_request_requires_a_structured_goal() -> None:
    request = PlanRequest.model_validate(
        {"goal": {"objective": "制定北京三日游计划"}, "max_tasks": 8}
    )

    assert request.goal.to_domain().objective == "制定北京三日游计划"
    assert request.max_tasks == 8
    assert any(route.path == "/plan" for route in app.routes)


def test_plan_endpoint_returns_a_runtime_validated_plan(monkeypatch) -> None:
    class Client:
        def complete(self, messages, tools):
            assert tools == []
            content = json.dumps(
                {
                    "tasks": [
                        {
                            "key": "research",
                            "title": "查询信息",
                            "description": "收集交通、住宿和景点信息",
                            "depends_on": [],
                            "completion_criteria": ["信息具有明确来源"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
            return ModelResponse(
                message=Message(role="assistant", content=content),
                finish_reason="stop",
            )

    monkeypatch.setattr(main, "_build_client", lambda: Client())
    request = PlanRequest.model_validate(
        {"goal": {"objective": "制定北京三日游计划"}}
    )

    response = main.plan_tasks(request)

    assert response["schema_version"] == "task-plan/v1"
    assert response["goal_id"] == request.goal.id
    assert response["tasks"][0]["status"] == "pending"
