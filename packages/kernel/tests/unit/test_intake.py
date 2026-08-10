"""Tests for natural-language Goal intake."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from loopbase import (
    GoalIntake,
    IntakeGenerationError,
    IntakeStatus,
    Message,
    ModelResponse,
)


@dataclass
class IntakeClient:
    content: str

    def complete(self, messages, tools):
        assert tools == []
        assert messages[-1].role == "user"
        return ModelResponse(
            message=Message(role="assistant", content=self.content),
            finish_reason="stop",
        )


def _proposal(**overrides) -> dict:
    result = {
        "objective": "制定深圳3天2夜旅行攻略",
        "success_criteria": ["给出三天每日行程", "列出预算明细"],
        "constraints": ["总预算不超过5000元"],
        "context": {
            "destination_city": "深圳",
            "days": 3,
            "nights": 2,
            "budget": 5000,
        },
        "missing_information": [],
        "questions": [],
    }
    result.update(overrides)
    return result


def test_intake_builds_a_goal_from_one_travel_prompt() -> None:
    prompt = "深圳旅行攻略3天2夜，预算5000"
    intake = GoalIntake(
        client=IntakeClient(json.dumps(_proposal(), ensure_ascii=False))
    )

    result = intake.intake(prompt)

    assert result.status is IntakeStatus.READY
    assert result.goal is not None
    assert result.goal.objective == "制定深圳3天2夜旅行攻略"
    assert result.goal.constraints == ("总预算不超过5000元",)
    assert result.goal.context["destination_city"] == "深圳"
    assert result.goal.context["original_prompt"] == prompt


def test_intake_returns_questions_when_destination_is_missing() -> None:
    proposal = _proposal(
        objective="制定3天2夜旅行攻略",
        context={"days": 3, "nights": 2},
        missing_information=["destination_city"],
        questions=["你想去哪个城市？"],
    )

    result = GoalIntake(
        client=IntakeClient(json.dumps(proposal, ensure_ascii=False))
    ).intake("帮我安排3天2夜旅行")

    assert result.status is IntakeStatus.NEEDS_CLARIFICATION
    assert result.goal is None
    assert result.missing_information == ("destination_city",)
    assert result.questions == ("你想去哪个城市？",)


def test_intake_rejects_invalid_json() -> None:
    with pytest.raises(IntakeGenerationError, match="invalid JSON"):
        GoalIntake(client=IntakeClient("not json")).intake("深圳三日游")


def test_intake_rejects_unpaired_missing_information_and_questions() -> None:
    proposal = _proposal(
        missing_information=["destination_city"],
        questions=[],
    )

    with pytest.raises(IntakeGenerationError, match="must both be"):
        GoalIntake(
            client=IntakeClient(json.dumps(proposal, ensure_ascii=False))
        ).intake("帮我旅行")
