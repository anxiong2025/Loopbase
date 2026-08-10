"""Layer 4 — task plans, dependencies, and lifecycle state."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

TASK_PLAN_SCHEMA_VERSION = "task-plan/v1"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED}),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED}
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.PENDING, TaskStatus.FAILED}),
    TaskStatus.FAILED: frozenset({TaskStatus.PENDING}),
    TaskStatus.COMPLETED: frozenset(),
}


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _text_tuple(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple of strings")
    return tuple(_text(value, f"{field_name} entry") for value in values)


def _timestamp(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number")
    return float(value)


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    goal_id: str
    title: str
    description: str
    depends_on: tuple[str, ...] = ()
    completion_criteria: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        task_id = _text(self.id, "id")
        goal_id = _text(self.goal_id, "goal_id")
        title = _text(self.title, "title")
        description = _text(self.description, "description")
        depends_on = _text_tuple(self.depends_on, "depends_on")
        criteria = _text_tuple(self.completion_criteria, "completion_criteria")
        created_at = _timestamp(self.created_at, "created_at")
        updated_at = _timestamp(self.updated_at, "updated_at")
        try:
            status = TaskStatus(self.status)
        except ValueError as exc:
            raise ValueError(f"unknown task status: {self.status!r}") from exc
        if task_id in depends_on:
            raise ValueError(f"task {task_id!r} cannot depend on itself")
        if len(depends_on) != len(set(depends_on)):
            raise ValueError(f"task {task_id!r} contains duplicate dependencies")
        if updated_at < created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        object.__setattr__(self, "id", task_id)
        object.__setattr__(self, "goal_id", goal_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "depends_on", depends_on)
        object.__setattr__(self, "completion_criteria", criteria)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)

    def transition(self, status: TaskStatus, *, at: float | None = None) -> Task:
        target = TaskStatus(status)
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"invalid task transition: {self.status.value} -> {target.value}"
            )
        changed_at = time.time() if at is None else _timestamp(at, "at")
        if changed_at < self.updated_at:
            raise ValueError("transition time cannot move backwards")
        return replace(self, status=target, updated_at=changed_at)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "depends_on": list(self.depends_on),
            "completion_criteria": list(self.completion_criteria),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        required = {
            "id",
            "goal_id",
            "title",
            "description",
            "depends_on",
            "completion_criteria",
            "status",
            "created_at",
            "updated_at",
        }
        if not isinstance(data, dict):
            raise TypeError("task data must be a JSON object")
        missing = required - data.keys()
        unknown = data.keys() - required
        if missing:
            raise ValueError(f"task data is missing required fields: {sorted(missing)}")
        if unknown:
            raise ValueError(f"task data contains unknown fields: {sorted(unknown)}")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class TaskPlan:
    goal_id: str
    tasks: tuple[Task, ...]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    schema_version: str = TASK_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        plan_id = _text(self.id, "id")
        goal_id = _text(self.goal_id, "goal_id")
        if self.schema_version != TASK_PLAN_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported task-plan schema version: {self.schema_version!r}"
            )
        if not isinstance(self.tasks, (list, tuple)) or not self.tasks:
            raise ValueError("a task plan must contain at least one task")
        tasks = tuple(self.tasks)
        if not all(isinstance(task, Task) for task in tasks):
            raise TypeError("tasks must contain only Task values")
        created_at = _timestamp(self.created_at, "created_at")

        task_ids = [task.id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task ids must be unique within a plan")
        known_ids = set(task_ids)
        for task in tasks:
            if task.goal_id != goal_id:
                raise ValueError(f"task {task.id!r} belongs to a different goal")
            unknown = set(task.depends_on) - known_ids
            if unknown:
                raise ValueError(
                    f"task {task.id!r} has unknown dependencies: {sorted(unknown)}"
                )
        self._assert_acyclic(tasks)

        object.__setattr__(self, "id", plan_id)
        object.__setattr__(self, "goal_id", goal_id)
        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "created_at", created_at)

    @staticmethod
    def _assert_acyclic(tasks: tuple[Task, ...]) -> None:
        dependencies = {task.id: task.depends_on for task in tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("task dependencies must not contain a cycle")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency_id in dependencies[task_id]:
                visit(dependency_id)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in dependencies:
            visit(task_id)

    def get(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"unknown task: {task_id}")

    def ready_tasks(self) -> tuple[Task, ...]:
        statuses = {task.id: task.status for task in self.tasks}
        return tuple(
            task
            for task in self.tasks
            if task.status is TaskStatus.PENDING
            and all(statuses[item] is TaskStatus.COMPLETED for item in task.depends_on)
        )

    def transition(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        at: float | None = None,
    ) -> TaskPlan:
        current = self.get(task_id)
        target = TaskStatus(status)
        if target is TaskStatus.IN_PROGRESS:
            statuses = {task.id: task.status for task in self.tasks}
            incomplete = [
                item
                for item in current.depends_on
                if statuses[item] is not TaskStatus.COMPLETED
            ]
            if incomplete:
                raise ValueError(
                    f"task {task_id!r} has incomplete dependencies: {incomplete}"
                )
        updated = current.transition(target, at=at)
        tasks = tuple(updated if task.id == task_id else task for task in self.tasks)
        return replace(self, tasks=tasks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "goal_id": self.goal_id,
            "tasks": [task.as_dict() for task in self.tasks],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskPlan:
        required = {"schema_version", "id", "goal_id", "tasks", "created_at"}
        if not isinstance(data, dict):
            raise TypeError("task-plan data must be a JSON object")
        missing = required - data.keys()
        unknown = data.keys() - required
        if missing:
            raise ValueError(
                f"task-plan data is missing required fields: {sorted(missing)}"
            )
        if unknown:
            raise ValueError(
                f"task-plan data contains unknown fields: {sorted(unknown)}"
            )
        return cls(
            schema_version=data["schema_version"],
            id=data["id"],
            goal_id=data["goal_id"],
            tasks=tuple(Task.from_dict(item) for item in data["tasks"]),
            created_at=data["created_at"],
        )
