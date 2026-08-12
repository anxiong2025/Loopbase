"""Stage 2 task planning: model proposes, runtime validates and owns state."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .goals import Goal
from .models.base import Message, ModelClient
from .observability import Actor, EventKind
from .state import EvidenceLog
from .tasks import Task, TaskPlan


class PlanGenerationError(RuntimeError):
    """The model did not return a valid task-plan proposal."""


@dataclass(frozen=True, slots=True)
class PlanningResult:
    """A validated plan together with the untouched model response."""

    plan: TaskPlan
    raw_model_content: str
    finish_reason: str
    usage: dict[str, Any] | None
    provider_response: dict[str, Any]

    def raw_response_as_dict(self) -> dict[str, Any]:
        return {
            "content": self.raw_model_content,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "provider_response": self.provider_response,
        }


_PROPOSAL_FIELDS = {
    "key",
    "title",
    "description",
    "depends_on",
    "completion_criteria",
}


class TaskPlanner:
    """Ask a model for a task proposal, then build a validated ``TaskPlan``.

    The model never assigns runtime ids or lifecycle states.  It emits local
    dependency keys; the runtime maps those keys to ids, sets every initial
    status to ``pending``, and rejects malformed or cyclic plans.
    """

    def __init__(
        self,
        *,
        client: ModelClient,
        max_tasks: int = 12,
        evidence_log: EvidenceLog | None = None,
    ) -> None:
        if isinstance(max_tasks, bool) or not isinstance(max_tasks, int) or max_tasks < 1:
            raise ValueError("max_tasks must be a positive integer")
        self.client = client
        self.max_tasks = max_tasks
        self.evidence_log = evidence_log

    def plan(self, goal: Goal) -> TaskPlan:
        return self.plan_with_trace(goal).plan

    def plan_with_trace(self, goal: Goal) -> PlanningResult:
        """Plan once and retain the response exactly as returned by the client."""

        if not isinstance(goal, Goal):
            raise TypeError("goal must be a Goal")
        start_event = self._log(EventKind.PLAN_START, {"goal": goal.as_dict()})
        messages = [
            Message(role="system", content=self._system_prompt()),
            Message(
                role="user",
                content="Create a task plan for this goal:\n"
                + json.dumps(goal.model_payload(), ensure_ascii=False, indent=2),
            ),
        ]
        try:
            response = self.client.complete(messages, [])
            if response.finish_reason != "stop" or response.message.tool_calls:
                raise PlanGenerationError("planner must return one final JSON response")
            proposal = _parse_json_object(response.message.content)
            plan = self._build_plan(goal, proposal)
        except Exception as exc:
            self._log(
                EventKind.PLAN_FAILED,
                {
                    "goal_id": goal.id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                caused_by=start_event,
            )
            raise

        self._log(
            EventKind.PLAN_CREATED,
            {"task_plan": plan.as_dict()},
            caused_by=start_event,
        )
        return PlanningResult(
            plan=plan,
            raw_model_content=response.message.content,
            finish_reason=response.finish_reason,
            usage=response.usage,
            provider_response=response.raw,
        )

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
            kind, payload, actor=Actor.PLANNER, caused_by=caused_by
        ).id

    def _system_prompt(self) -> str:
        return f"""You are a task planner inside an agent runtime.
Return JSON only, with no prose and no markdown fence.

Schema:
{{
  "tasks": [
    {{
      "key": "short_local_key",
      "title": "short task title",
      "description": "what the task must do",
      "depends_on": ["another_key"],
      "completion_criteria": ["observable condition"]
    }}
  ]
}}

Rules:
- Produce between 1 and {self.max_tasks} executable tasks.
- Keys must be unique and dependencies must reference keys in this response.
- Dependencies must be acyclic.
- Cover the goal's success criteria and constraints.
- Include a final validation task when the result must satisfy multiple constraints.
- Do not assign ids, statuses, agents, tools, or invented user requirements.
- Do not include clarification tasks; this planner receives an already accepted goal.
"""

    def _build_plan(self, goal: Goal, proposal: dict[str, Any]) -> TaskPlan:
        if set(proposal) != {"tasks"}:
            raise PlanGenerationError("planner response must contain only a tasks field")
        items = proposal["tasks"]
        if not isinstance(items, list) or not 1 <= len(items) <= self.max_tasks:
            raise PlanGenerationError(
                f"planner must return between 1 and {self.max_tasks} tasks"
            )

        normalized: list[dict[str, Any]] = []
        keys: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or set(item) != _PROPOSAL_FIELDS:
                raise PlanGenerationError(
                    f"task proposal {index} has an invalid field set"
                )
            key = _proposal_text(item["key"], f"tasks[{index}].key")
            title = _proposal_text(item["title"], f"tasks[{index}].title")
            description = _proposal_text(
                item["description"], f"tasks[{index}].description"
            )
            depends_on = _proposal_text_list(
                item["depends_on"], f"tasks[{index}].depends_on"
            )
            criteria = _proposal_text_list(
                item["completion_criteria"],
                f"tasks[{index}].completion_criteria",
            )
            keys.append(key)
            normalized.append(
                {
                    "key": key,
                    "title": title,
                    "description": description,
                    "depends_on": depends_on,
                    "completion_criteria": criteria,
                }
            )

        if len(keys) != len(set(keys)):
            raise PlanGenerationError("task proposal keys must be unique")
        known_keys = set(keys)
        for item in normalized:
            unknown = set(item["depends_on"]) - known_keys
            if unknown:
                raise PlanGenerationError(
                    f"task {item['key']!r} has unknown dependencies: {sorted(unknown)}"
                )

        ids = {key: uuid.uuid4().hex for key in keys}
        now = time.time()
        try:
            tasks = tuple(
                Task(
                    id=ids[item["key"]],
                    goal_id=goal.id,
                    title=item["title"],
                    description=item["description"],
                    depends_on=tuple(ids[key] for key in item["depends_on"]),
                    completion_criteria=item["completion_criteria"],
                    created_at=now,
                    updated_at=now,
                )
                for item in normalized
            )
            return TaskPlan(goal_id=goal.id, tasks=tasks, created_at=now)
        except (TypeError, ValueError) as exc:
            raise PlanGenerationError(f"invalid task plan: {exc}") from exc


def _parse_json_object(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise PlanGenerationError("planner returned empty content")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise PlanGenerationError("planner returned an incomplete JSON fence")
        text = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanGenerationError(f"planner returned invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise PlanGenerationError("planner response must be a JSON object")
    return data


def _proposal_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanGenerationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _proposal_text_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PlanGenerationError(f"{field_name} must be an array")
    result = tuple(
        _proposal_text(item, f"{field_name} entry") for item in value
    )
    if len(result) != len(set(result)):
        raise PlanGenerationError(f"{field_name} must not contain duplicates")
    return result
