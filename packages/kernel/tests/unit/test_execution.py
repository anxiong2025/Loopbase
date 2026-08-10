"""Tests for serial TaskPlan execution through a ReAct-compatible runner."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from loopbase import (
    ExecutionStatus,
    Goal,
    RunResult,
    Task,
    TaskExecutor,
    TaskPlan,
    TaskStatus,
)


def _goal() -> Goal:
    return Goal(
        id="goal_trip",
        objective="制定北京三日游计划",
        success_criteria=("给出三天行程", "列出费用"),
        constraints=("预算不超过3000元",),
        context={"origin": "深圳", "destination": "北京"},
        created_at=1.0,
    )


def _task(
    task_id: str,
    title: str,
    *,
    depends_on: tuple[str, ...] = (),
) -> Task:
    return Task(
        id=task_id,
        goal_id="goal_trip",
        title=title,
        description=f"完成{title}",
        depends_on=depends_on,
        completion_criteria=(f"{title}有明确结果",),
        created_at=1.0,
        updated_at=1.0,
    )


@dataclass
class SuccessfulRunner:
    goals: list[Goal] = field(default_factory=list)

    def run(self, goal: Goal) -> RunResult:
        self.goals.append(goal)
        return RunResult(
            final_answer=f"已完成：{goal.objective.splitlines()[0]}",
            turns=2,
            goal=goal,
            tool_calls_executed=["fake_tool"],
            stopped_by="model",
        )


def test_executor_runs_tasks_in_dependency_order_and_passes_results() -> None:
    plan = TaskPlan(
        id="plan_trip",
        goal_id="goal_trip",
        tasks=(
            _task("research", "收集信息"),
            _task("itinerary", "规划行程", depends_on=("research",)),
        ),
        created_at=1.0,
    )
    runner = SuccessfulRunner()

    result = TaskExecutor(runner=runner).execute(_goal(), plan)

    assert result.status is ExecutionStatus.COMPLETED
    assert [task.status for task in result.task_plan.tasks] == [
        TaskStatus.COMPLETED,
        TaskStatus.COMPLETED,
    ]
    assert [goal.id for goal in runner.goals] == ["research", "itinerary"]
    assert runner.goals[1].context["dependency_results"] == [
        {
            "task_id": "research",
            "title": "收集信息",
            "output": "已完成：收集信息",
        }
    ]
    assert result.final_answer == "已完成：规划行程"
    assert result.task_records[0].tool_calls_executed == ("fake_tool",)


def test_executor_marks_max_turn_task_failed_and_dependents_blocked() -> None:
    class MaxTurnRunner:
        def run(self, goal: Goal) -> RunResult:
            return RunResult(
                final_answer=None,
                turns=3,
                goal=goal,
                stopped_by="max_turns",
            )

    plan = TaskPlan(
        goal_id="goal_trip",
        tasks=(
            _task("research", "收集信息"),
            _task("itinerary", "规划行程", depends_on=("research",)),
        ),
        created_at=1.0,
    )

    result = TaskExecutor(runner=MaxTurnRunner()).execute(_goal(), plan)

    assert result.status is ExecutionStatus.FAILED
    assert result.task_plan.get("research").status is TaskStatus.FAILED
    assert result.task_plan.get("itinerary").status is TaskStatus.BLOCKED
    assert result.task_records[0].turns == 3
    assert result.task_records[0].stopped_by == "max_turns"
    assert "stopped by max_turns" in (result.task_records[0].error or "")


def test_executor_continues_an_independent_branch_after_failure() -> None:
    class BranchRunner:
        def run(self, goal: Goal) -> RunResult:
            if goal.id == "broken":
                raise RuntimeError("tool unavailable")
            return RunResult(
                final_answer="independent result",
                turns=1,
                goal=goal,
                stopped_by="model",
            )

    plan = TaskPlan(
        goal_id="goal_trip",
        tasks=(
            _task("broken", "失败分支"),
            _task("independent", "独立分支"),
            _task("dependent", "依赖任务", depends_on=("broken",)),
        ),
        created_at=1.0,
    )

    result = TaskExecutor(runner=BranchRunner()).execute(_goal(), plan)

    assert result.status is ExecutionStatus.FAILED
    assert result.task_plan.get("broken").status is TaskStatus.FAILED
    assert result.task_plan.get("independent").status is TaskStatus.COMPLETED
    assert result.task_plan.get("dependent").status is TaskStatus.BLOCKED
    assert [record.task_id for record in result.task_records] == [
        "broken",
        "independent",
    ]


def test_executor_rejects_a_plan_for_another_goal() -> None:
    plan = TaskPlan(
        goal_id="another_goal",
        tasks=(
            Task(
                id="task",
                goal_id="another_goal",
                title="任务",
                description="任务描述",
            ),
        ),
    )

    with pytest.raises(ValueError, match="must match"):
        TaskExecutor(runner=SuccessfulRunner()).execute(_goal(), plan)
