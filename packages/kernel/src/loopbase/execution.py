"""Stage 2 task execution: run a validated plan through one ReAct worker."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .goals import Goal
from .loop import RunResult
from .tasks import Task, TaskPlan, TaskStatus

EXECUTION_RESULT_SCHEMA_VERSION = "execution-result/v1"


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class GoalRunner(Protocol):
    """The narrow interface TaskExecutor needs from a ReAct worker."""

    def run(self, goal: Goal) -> RunResult: ...


@dataclass(frozen=True, slots=True)
class TaskExecutionRecord:
    task_id: str
    status: TaskStatus
    output: str | None
    error: str | None
    turns: int
    stopped_by: str
    tool_calls_executed: tuple[str, ...]
    started_at: float
    finished_at: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "turns": self.turns,
            "stopped_by": self.stopped_by,
            "tool_calls_executed": list(self.tool_calls_executed),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    goal_id: str
    task_plan: TaskPlan
    task_records: tuple[TaskExecutionRecord, ...]
    status: ExecutionStatus
    final_answer: str | None
    schema_version: str = EXECUTION_RESULT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "final_answer": self.final_answer,
            "task_plan": self.task_plan.as_dict(),
            "task_records": [record.as_dict() for record in self.task_records],
        }


class TaskExecutor:
    """Execute ready tasks serially and let TaskPlan own lifecycle state."""

    def __init__(self, *, runner: GoalRunner) -> None:
        self.runner = runner

    def execute(self, goal: Goal, task_plan: TaskPlan) -> ExecutionResult:
        if not isinstance(goal, Goal):
            raise TypeError("goal must be a Goal")
        if not isinstance(task_plan, TaskPlan):
            raise TypeError("task_plan must be a TaskPlan")
        if task_plan.goal_id != goal.id:
            raise ValueError("task_plan.goal_id must match goal.id")
        if any(task.status is not TaskStatus.PENDING for task in task_plan.tasks):
            raise ValueError("a new execution requires every task to be pending")

        current = task_plan
        records: list[TaskExecutionRecord] = []
        outputs: dict[str, str] = {}

        while ready := current.ready_tasks():
            task = ready[0]
            current = current.transition(task.id, TaskStatus.IN_PROGRESS)
            started_at = time.time()
            task_goal = self._task_goal(goal, current, task, outputs)
            run_result: RunResult | None = None

            try:
                run_result = self.runner.run(task_goal)
                if run_result.stopped_by != "model" or not run_result.final_answer:
                    reason = run_result.stopped_by or "without_final_answer"
                    raise RuntimeError(f"task ReAct loop stopped by {reason}")
            except Exception as exc:  # noqa: BLE001 - one failed task must not crash the plan
                finished_at = time.time()
                current = current.transition(task.id, TaskStatus.FAILED)
                records.append(
                    TaskExecutionRecord(
                        task_id=task.id,
                        status=TaskStatus.FAILED,
                        output=None,
                        error=str(exc),
                        turns=run_result.turns if run_result is not None else 0,
                        stopped_by=(
                            run_result.stopped_by
                            if run_result is not None
                            else "exception"
                        ),
                        tool_calls_executed=tuple(
                            run_result.tool_calls_executed
                            if run_result is not None
                            else ()
                        ),
                        started_at=started_at,
                        finished_at=finished_at,
                    )
                )
                current = self._block_failed_dependents(current)
                continue

            finished_at = time.time()
            output = run_result.final_answer
            outputs[task.id] = output
            current = current.transition(task.id, TaskStatus.COMPLETED)
            records.append(
                TaskExecutionRecord(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    output=output,
                    error=None,
                    turns=run_result.turns,
                    stopped_by=run_result.stopped_by,
                    tool_calls_executed=tuple(run_result.tool_calls_executed),
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )

        status = self._execution_status(current)
        final_answer = records[-1].output if status is ExecutionStatus.COMPLETED else None
        return ExecutionResult(
            goal_id=goal.id,
            task_plan=current,
            task_records=tuple(records),
            status=status,
            final_answer=final_answer,
        )

    @staticmethod
    def _task_goal(
        parent_goal: Goal,
        task_plan: TaskPlan,
        task: Task,
        outputs: dict[str, str],
    ) -> Goal:
        dependency_results = [
            {
                "task_id": dependency_id,
                "title": task_plan.get(dependency_id).title,
                "output": outputs[dependency_id],
            }
            for dependency_id in task.depends_on
        ]
        return Goal(
            id=task.id,
            objective=f"{task.title}\n\n{task.description}",
            success_criteria=(
                task.completion_criteria or parent_goal.success_criteria
            ),
            constraints=parent_goal.constraints,
            context={
                "parent_goal_id": parent_goal.id,
                "parent_goal_context": parent_goal.context,
                "task_id": task.id,
                "dependency_results": dependency_results,
            },
        )

    @staticmethod
    def _block_failed_dependents(task_plan: TaskPlan) -> TaskPlan:
        current = task_plan
        changed = True
        while changed:
            changed = False
            statuses = {task.id: task.status for task in current.tasks}
            for task in current.tasks:
                if task.status is not TaskStatus.PENDING:
                    continue
                if any(
                    statuses[dependency]
                    in {TaskStatus.FAILED, TaskStatus.BLOCKED}
                    for dependency in task.depends_on
                ):
                    current = current.transition(task.id, TaskStatus.BLOCKED)
                    changed = True
        return current

    @staticmethod
    def _execution_status(task_plan: TaskPlan) -> ExecutionStatus:
        statuses = {task.status for task in task_plan.tasks}
        if statuses == {TaskStatus.COMPLETED}:
            return ExecutionStatus.COMPLETED
        if TaskStatus.FAILED in statuses:
            return ExecutionStatus.FAILED
        return ExecutionStatus.BLOCKED
