"""Stage 2 task-plan and lifecycle tests."""

from __future__ import annotations

import pytest

from loopbase import Task, TaskPlan, TaskStatus


def _task(
    task_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    status: TaskStatus = TaskStatus.PENDING,
) -> Task:
    return Task(
        id=task_id,
        goal_id="goal_1",
        title=f"Task {task_id}",
        description=f"Execute {task_id}",
        depends_on=depends_on,
        completion_criteria=(f"{task_id} is verified",),
        status=status,
        created_at=1.0,
        updated_at=1.0,
    )


def test_task_plan_tracks_ready_tasks_and_dependencies() -> None:
    plan = TaskPlan(
        id="plan_1",
        goal_id="goal_1",
        tasks=(_task("research"), _task("write", depends_on=("research",))),
        created_at=1.0,
    )

    assert [task.id for task in plan.ready_tasks()] == ["research"]
    with pytest.raises(ValueError, match="incomplete dependencies"):
        plan.transition("write", TaskStatus.IN_PROGRESS, at=2.0)

    plan = plan.transition("research", TaskStatus.IN_PROGRESS, at=2.0)
    plan = plan.transition("research", TaskStatus.COMPLETED, at=3.0)

    assert [task.id for task in plan.ready_tasks()] == ["write"]


def test_task_plan_rejects_cycles() -> None:
    with pytest.raises(ValueError, match="cycle"):
        TaskPlan(
            goal_id="goal_1",
            tasks=(
                _task("a", depends_on=("b",)),
                _task("b", depends_on=("a",)),
            ),
        )


def test_task_status_transition_rules_are_enforced() -> None:
    task = _task("research")

    with pytest.raises(ValueError, match="invalid task transition"):
        task.transition(TaskStatus.COMPLETED, at=2.0)

    running = task.transition(TaskStatus.IN_PROGRESS, at=2.0)
    completed = running.transition(TaskStatus.COMPLETED, at=3.0)

    assert completed.status is TaskStatus.COMPLETED
    with pytest.raises(ValueError, match="invalid task transition"):
        completed.transition(TaskStatus.IN_PROGRESS, at=4.0)


def test_task_plan_round_trips_through_v1_dict() -> None:
    plan = TaskPlan(
        id="plan_1",
        goal_id="goal_1",
        tasks=(_task("research"), _task("write", depends_on=("research",))),
        created_at=1.0,
    )

    assert TaskPlan.from_dict(plan.as_dict()) == plan
