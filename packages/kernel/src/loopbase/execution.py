"""Stage 2 task execution: run a validated plan through one ReAct worker.

Stage 4 起，执行器的每一次状态转移都写进证据日志，并且可以从日志里重建出来
继续跑（``resume``）。这两件事是一体的：只有转移全部被记下来，重建才是可能的。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .goals import Goal
from .loop import RunResult
from .observability import Actor, EventKind
from .state import EvidenceLog, ReplayedRun
from .tasks import Task, TaskPlan, TaskStatus

EXECUTION_RESULT_SCHEMA_VERSION = "execution-result/v1"


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class GoalRunner(Protocol):
    """The narrow interface TaskExecutor needs from a ReAct worker.

    ``caused_by`` carries the delegating event id so the worker's own events hang
    under it in the causal chain; an implementation may ignore it.
    """

    def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult: ...


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskExecutionRecord:
        """Rebuild a record replayed out of the evidence log."""
        required = {
            "task_id",
            "status",
            "output",
            "error",
            "turns",
            "stopped_by",
            "tool_calls_executed",
            "started_at",
            "finished_at",
        }
        if not isinstance(data, dict):
            raise TypeError("task execution record must be a JSON object")
        missing = required - data.keys()
        unknown = data.keys() - required
        if missing:
            raise ValueError(
                f"task execution record is missing required fields: {sorted(missing)}"
            )
        if unknown:
            raise ValueError(
                f"task execution record contains unknown fields: {sorted(unknown)}"
            )
        return cls(
            task_id=data["task_id"],
            status=TaskStatus(data["status"]),
            output=data["output"],
            error=data["error"],
            turns=data["turns"],
            stopped_by=data["stopped_by"],
            tool_calls_executed=tuple(data["tool_calls_executed"]),
            started_at=data["started_at"],
            finished_at=data["finished_at"],
        )


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

    def __init__(
        self,
        *,
        runner: GoalRunner,
        evidence_log: EvidenceLog | None = None,
    ) -> None:
        self.runner = runner
        self.evidence_log = evidence_log

    def execute(self, goal: Goal, task_plan: TaskPlan) -> ExecutionResult:
        if not isinstance(goal, Goal):
            raise TypeError("goal must be a Goal")
        if not isinstance(task_plan, TaskPlan):
            raise TypeError("task_plan must be a TaskPlan")
        if task_plan.goal_id != goal.id:
            raise ValueError("task_plan.goal_id must match goal.id")
        if any(task.status is not TaskStatus.PENDING for task in task_plan.tasks):
            raise ValueError("a new execution requires every task to be pending")

        root_event = self._log(
            EventKind.EXECUTION_START,
            {"goal": goal.as_dict(), "task_plan": task_plan.as_dict()},
        )
        return self._drive(goal, task_plan, {}, [], root_event)

    def resume(self, replayed: ReplayedRun) -> ExecutionResult:
        """Continue a run that was reconstructed from its event log.

        Tasks interrupted mid-flight are re-opened and run again from the start —
        see ``ReplayedRun.resumable_plan`` for why, and what it costs.
        """
        if not isinstance(replayed, ReplayedRun):
            raise TypeError("replayed must be a ReplayedRun")
        goal = replayed.require_goal()
        plan = replayed.resumable_plan()
        outputs = dict(replayed.outputs)
        records = [
            TaskExecutionRecord.from_dict(payload)
            for payload in replayed.task_record_payloads
        ]

        root_event = self._log(
            EventKind.EXECUTION_RESUMED,
            {
                "goal": goal.as_dict(),
                "task_plan": plan.as_dict(),
                "outputs": outputs,
                "task_records": [record.as_dict() for record in records],
                "resumed_from_run_id": replayed.run_id,
                "interrupted_task_ids": list(replayed.interrupted_task_ids),
            },
        )
        return self._drive(goal, plan, outputs, records, root_event)

    def _drive(
        self,
        goal: Goal,
        task_plan: TaskPlan,
        outputs: dict[str, str],
        records: list[TaskExecutionRecord],
        root_event: str | None,
    ) -> ExecutionResult:
        current = task_plan

        while ready := current.ready_tasks():
            task = ready[0]
            started_at = time.time()
            current = current.transition(
                task.id, TaskStatus.IN_PROGRESS, at=started_at
            )
            start_event = self._log(
                EventKind.TASK_STARTED,
                {"task_id": task.id, "title": task.title, "at": started_at},
                caused_by=root_event,
            )
            task_goal = self._task_goal(goal, current, task, outputs)
            run_result: RunResult | None = None

            try:
                run_result = self.runner.run(task_goal, caused_by=start_event)
                if run_result.stopped_by != "model" or not run_result.final_answer:
                    reason = run_result.stopped_by or "without_final_answer"
                    raise RuntimeError(f"task ReAct loop stopped by {reason}")
            except Exception as exc:  # noqa: BLE001 - one failed task must not crash the plan
                finished_at = time.time()
                current = current.transition(
                    task.id, TaskStatus.FAILED, at=finished_at
                )
                record = TaskExecutionRecord(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    output=None,
                    error=str(exc),
                    turns=run_result.turns if run_result is not None else 0,
                    stopped_by=(
                        run_result.stopped_by if run_result is not None else "exception"
                    ),
                    tool_calls_executed=tuple(
                        run_result.tool_calls_executed if run_result is not None else ()
                    ),
                    started_at=started_at,
                    finished_at=finished_at,
                )
                records.append(record)
                self._log(
                    EventKind.TASK_FAILED,
                    {
                        "task_id": task.id,
                        "record": record.as_dict(),
                        "at": finished_at,
                    },
                    caused_by=start_event,
                )
                current = self._block_failed_dependents(
                    current, at=finished_at, caused_by=start_event
                )
                continue

            finished_at = time.time()
            output = run_result.final_answer
            outputs[task.id] = output
            current = current.transition(
                task.id, TaskStatus.COMPLETED, at=finished_at
            )
            record = TaskExecutionRecord(
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
            records.append(record)
            self._log(
                EventKind.TASK_COMPLETED,
                {"task_id": task.id, "record": record.as_dict(), "at": finished_at},
                caused_by=start_event,
            )

        status = self._execution_status(current)
        final_answer = records[-1].output if status is ExecutionStatus.COMPLETED else None
        self._log(
            EventKind.EXECUTION_FINISHED,
            {
                "goal_id": goal.id,
                "status": status.value,
                "final_answer": final_answer,
            },
            caused_by=root_event,
        )
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

    def _block_failed_dependents(
        self,
        task_plan: TaskPlan,
        *,
        at: float,
        caused_by: str | None = None,
    ) -> TaskPlan:
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
                    current = current.transition(task.id, TaskStatus.BLOCKED, at=at)
                    self._log(
                        EventKind.TASK_BLOCKED,
                        {
                            "task_id": task.id,
                            "at": at,
                            "blocked_by": [
                                dependency
                                for dependency in task.depends_on
                                if statuses[dependency]
                                in {TaskStatus.FAILED, TaskStatus.BLOCKED}
                            ],
                        },
                        caused_by=caused_by,
                    )
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

    def _log(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        caused_by: str | None = None,
    ) -> str | None:
        if self.evidence_log is None:
            return None
        return self.evidence_log.append(
            kind, payload, actor=Actor.EXECUTOR, caused_by=caused_by
        ).id
