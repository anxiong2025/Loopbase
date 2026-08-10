"""Stage 2 structured-goal tests."""

from __future__ import annotations

import json

import pytest

from loopbase import GOAL_SCHEMA_VERSION, Goal


def test_goal_round_trips_through_v1_dict() -> None:
    goal = Goal(
        objective="Compare tomorrow's weather in Tokyo and Osaka",
        success_criteria=["Report both forecasts", "Recommend which city to visit"],
        constraints=["Use current weather data"],
        context={"traveler": {"prefers": "sunny weather"}},
        id="goal_weather_1",
        created_at=123.0,
    )

    restored = Goal.from_dict(goal.as_dict())

    assert restored == goal
    assert restored.schema_version == GOAL_SCHEMA_VERSION
    assert json.loads(restored.to_user_message().split("\n", 1)[1]) == goal.model_payload()


@pytest.mark.parametrize("objective", ["", "   ", None])
def test_goal_rejects_empty_objective(objective) -> None:
    with pytest.raises(ValueError, match="objective"):
        Goal(objective=objective)


def test_goal_rejects_non_json_context() -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        Goal(objective="test", context={"bad": object()})


def test_goal_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported goal schema version"):
        Goal.from_dict({**Goal(objective="test").as_dict(), "schema_version": "goal/v999"})


def test_goal_loader_enforces_the_schema_shape() -> None:
    data = Goal(objective="test").as_dict()
    data.pop("constraints")
    with pytest.raises(ValueError, match="missing required fields"):
        Goal.from_dict(data)


@pytest.mark.parametrize("created_at", [-1, "now", True])
def test_goal_rejects_invalid_creation_time(created_at) -> None:
    with pytest.raises(ValueError, match="created_at"):
        Goal(objective="test", created_at=created_at)
