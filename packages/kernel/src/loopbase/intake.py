"""Natural-language goal intake for product-facing Agent entry points."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .goals import Goal
from .models.base import Message, ModelClient

INTAKE_RESULT_SCHEMA_VERSION = "intake-result/v1"


class IntakeGenerationError(RuntimeError):
    """The model did not return a valid goal-intake proposal."""


class IntakeStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass(frozen=True, slots=True)
class GoalIntakeResult:
    status: IntakeStatus
    goal: Goal | None
    goal_draft: dict[str, Any]
    missing_information: tuple[str, ...]
    questions: tuple[str, ...]
    raw_model_content: str
    finish_reason: str
    usage: dict[str, Any] | None
    provider_response: dict[str, Any]
    schema_version: str = INTAKE_RESULT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "goal": self.goal.as_dict() if self.goal is not None else None,
            "goal_draft": self.goal_draft,
            "missing_information": list(self.missing_information),
            "questions": list(self.questions),
        }

    def raw_response_as_dict(self) -> dict[str, Any]:
        return {
            "content": self.raw_model_content,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "provider_response": self.provider_response,
        }


class GoalIntake:
    """Turn one user prompt into a validated Goal or a small clarification set."""

    def __init__(self, *, client: ModelClient, max_questions: int = 3) -> None:
        if (
            isinstance(max_questions, bool)
            or not isinstance(max_questions, int)
            or not 1 <= max_questions <= 5
        ):
            raise ValueError("max_questions must be between 1 and 5")
        self.client = client
        self.max_questions = max_questions

    def intake(self, prompt: str) -> GoalIntakeResult:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        user_prompt = prompt.strip()
        messages = [
            Message(role="system", content=self._system_prompt()),
            Message(
                role="user",
                content="Convert this user request into a goal draft:\n" + user_prompt,
            ),
        ]
        response = self.client.complete(messages, [])
        if response.finish_reason != "stop" or response.message.tool_calls:
            raise IntakeGenerationError("goal intake must return one final JSON response")
        proposal = _parse_json_object(response.message.content)
        draft, missing, questions = self._validate_proposal(proposal, user_prompt)

        status = (
            IntakeStatus.NEEDS_CLARIFICATION if missing else IntakeStatus.READY
        )
        goal = None
        if status is IntakeStatus.READY:
            try:
                goal = Goal(**draft)
            except (TypeError, ValueError) as exc:
                raise IntakeGenerationError(f"invalid goal draft: {exc}") from exc

        return GoalIntakeResult(
            status=status,
            goal=goal,
            goal_draft=draft,
            missing_information=missing,
            questions=questions,
            raw_model_content=response.message.content,
            finish_reason=response.finish_reason,
            usage=response.usage,
            provider_response=response.raw,
        )

    def _system_prompt(self) -> str:
        return f"""You are the goal-intake layer for a lazy-friendly travel agent.
Return JSON only, with no prose and no markdown fence.

Schema:
{{
  "objective": "one clear travel objective",
  "success_criteria": ["observable result"],
  "constraints": ["explicit user requirement"],
  "context": {{"structured_key": "known value"}},
  "missing_information": ["blocking field name"],
  "questions": ["one concise question for the user"]
}}

Rules:
- Preserve every explicit fact from the user, especially destination, origin, dates, duration, nights, people, budget, and preferences.
- Never invent a destination, origin, date, budget, number of people, transport price, or hotel price.
- Infer useful output criteria, such as daily itinerary and budget breakdown, but do not turn inferred preferences into hard constraints.
- Ask only for information that blocks a useful plan. A destination-only itinerary does not require an origin. A generic guide does not require exact dates. Budget is optional unless the user asks to stay within an unspecified budget.
- Exact dates are blocking only when the user explicitly requests date-sensitive weather, availability, or booking information.
- If clarification is required, return at most {self.max_questions} questions. Otherwise both missing_information and questions must be empty arrays.
- Context values must be JSON values. Use days and nights as numbers and budget as a number when the user provides them.
"""

    def _validate_proposal(
        self,
        proposal: dict[str, Any],
        user_prompt: str,
    ) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
        fields = {
            "objective",
            "success_criteria",
            "constraints",
            "context",
            "missing_information",
            "questions",
        }
        if set(proposal) != fields:
            raise IntakeGenerationError(
                "goal intake response has an invalid field set"
            )
        objective = _text(proposal["objective"], "objective")
        criteria = _text_list(proposal["success_criteria"], "success_criteria")
        constraints = _text_list(proposal["constraints"], "constraints")
        missing = _text_list(
            proposal["missing_information"], "missing_information"
        )
        questions = _text_list(proposal["questions"], "questions")
        context = proposal["context"]
        if not isinstance(context, dict):
            raise IntakeGenerationError("context must be a JSON object")
        try:
            json.dumps(context, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise IntakeGenerationError("context must contain JSON values") from exc
        if len(questions) > self.max_questions:
            raise IntakeGenerationError("goal intake returned too many questions")
        if bool(missing) != bool(questions):
            raise IntakeGenerationError(
                "missing_information and questions must both be empty or non-empty"
            )

        normalized_context = dict(context)
        normalized_context["original_prompt"] = user_prompt
        draft = {
            "objective": objective,
            "success_criteria": criteria,
            "constraints": constraints,
            "context": normalized_context,
        }
        return draft, missing, questions


def _parse_json_object(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise IntakeGenerationError("goal intake returned empty content")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise IntakeGenerationError("goal intake returned an incomplete JSON fence")
        text = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IntakeGenerationError(
            f"goal intake returned invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise IntakeGenerationError("goal intake response must be a JSON object")
    return data


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntakeGenerationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _text_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise IntakeGenerationError(f"{field_name} must be an array")
    result = tuple(_text(item, f"{field_name} entry") for item in value)
    if len(result) != len(set(result)):
        raise IntakeGenerationError(f"{field_name} must not contain duplicates")
    return result
