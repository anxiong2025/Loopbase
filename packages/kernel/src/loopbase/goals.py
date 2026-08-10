"""Layer 4 — structured goal representation.

A goal is runtime data, not a sentence hidden inside a system prompt.  Stage 2
starts with this stable value object; task decomposition and replanning build on
top of it later.
"""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

GOAL_SCHEMA_VERSION = "goal/v1"
_GOAL_FIELDS = {
    "schema_version",
    "id",
    "objective",
    "success_criteria",
    "constraints",
    "context",
    "created_at",
}


def _normalize_text_items(
    values: tuple[str, ...] | list[str], field_name: str
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple of strings")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings")
        normalized.append(value.strip())
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class Goal:
    """A versioned, JSON-serializable objective accepted by the loop.

    ``success_criteria`` makes completion explicit, ``constraints`` records
    boundaries, and ``context`` carries structured facts supplied at creation.
    All fields are safe to persist in an event log.
    """

    objective: str
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    schema_version: str = GOAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, (int, float))
            or self.created_at < 0
        ):
            raise ValueError("created_at must be a non-negative number")
        if self.schema_version != GOAL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported goal schema version: {self.schema_version!r}; "
                f"expected {GOAL_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.context, dict):
            raise TypeError("context must be a JSON object")

        objective = self.objective.strip()
        criteria = _normalize_text_items(self.success_criteria, "success_criteria")
        constraints = _normalize_text_items(self.constraints, "constraints")
        context = deepcopy(self.context)
        try:
            json.dumps(context, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("context must contain only JSON-serializable values") from exc

        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "success_criteria", criteria)
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "id", self.id.strip())

    def as_dict(self) -> dict[str, Any]:
        """Return the language-neutral ``goal/v1`` representation."""
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "context": deepcopy(self.context),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Goal:
        """Load a goal while rejecting unknown schema versions."""
        if not isinstance(data, dict):
            raise TypeError("goal data must be a JSON object")
        missing = _GOAL_FIELDS - data.keys()
        if missing:
            raise ValueError(f"goal data is missing required fields: {sorted(missing)}")
        unknown = data.keys() - _GOAL_FIELDS
        if unknown:
            raise ValueError(f"goal data contains unknown fields: {sorted(unknown)}")
        version = data.get("schema_version")
        if version != GOAL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported goal schema version: {version!r}; "
                f"expected {GOAL_SCHEMA_VERSION!r}"
            )
        return cls(
            objective=data.get("objective"),
            success_criteria=data.get("success_criteria"),
            constraints=data.get("constraints"),
            context=data.get("context"),
            id=data.get("id"),
            created_at=data.get("created_at"),
            schema_version=version,
        )

    def model_payload(self) -> dict[str, Any]:
        """Return only the goal fields that help a model execute it."""
        return {
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "context": deepcopy(self.context),
        }

    def to_user_message(self) -> str:
        """Render a deterministic user message without hiding data in the system prompt."""
        return "Complete the following structured goal:\n" + json.dumps(
            self.model_payload(), ensure_ascii=False, indent=2
        )
