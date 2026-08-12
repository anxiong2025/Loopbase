"""Layer 9 — 可观测性：事件的**语义**定义。

这一层只回答「一条证据长什么样、有哪些种类」，不回答「写到哪去」——落盘是
Layer 7 (`state/`) 的事。这个切分是硬性的：observability 是横切层，任何层都
可以 import 它，它自己不 import 任何业务层（见 STRUCTURE.md 的层内规则）。

每条事件带三个身份字段，让日志可以脱离代码被审计：

- ``run_id``：属于哪一次运行。一个日志文件可以装多次运行。
- ``actor``：哪个内核组件写的（intake / planner / executor / loop）。
- ``caused_by``：触发它的那条事件 id，用来还原因果链。根事件为 None。

契约见 ``schemas/v1/event.schema.json``。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "event/v1"
#: 对外导出时用带前缀的名字，跟 goal/task-plan 的版本常量保持一致的命名。
EVENT_SCHEMA_VERSION = SCHEMA_VERSION

#: 缺字段的旧日志读回来时用的占位值，不伪造成看似真实的 id。
UNKNOWN = "unknown"


class Actor(StrEnum):
    """写下这条事件的内核组件。取值必须与 event.schema.json 的枚举一致。"""

    INTAKE = "intake"
    PLANNER = "planner"
    EXECUTOR = "executor"
    LOOP = "loop"
    KERNEL = "kernel"
    UNKNOWN = "unknown"


class EventKind(StrEnum):
    """事件种类。

    重放（``state.replay``）按这些常量还原状态，所以发事件的一方和读事件的一方
    必须用同一份定义，不能各写各的字符串字面量。
    """

    # intake
    INTAKE_START = "intake.start"
    INTAKE_COMPLETED = "intake.completed"
    INTAKE_NEEDS_CLARIFICATION = "intake.needs_clarification"
    INTAKE_FAILED = "intake.failed"

    # planner
    PLAN_START = "plan.start"
    PLAN_CREATED = "plan.created"
    PLAN_FAILED = "plan.failed"

    # executor
    EXECUTION_START = "execution.start"
    EXECUTION_RESUMED = "execution.resumed"
    EXECUTION_FINISHED = "execution.finished"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_BLOCKED = "task.blocked"

    # react loop
    GOAL_START = "goal.start"
    TURN_START = "turn.start"
    MODEL_RESPONSE = "model.response"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TOOL_ERROR = "tool.error"
    TURN_FINAL = "turn.final"
    TURN_MAX_TURNS = "turn.max_turns"


@dataclass
class EvidenceRecord:
    """一条不可变证据。kind 由调用方指定，payload 是任意结构化数据。"""

    kind: str
    payload: dict[str, Any]
    run_id: str
    actor: str
    caused_by: str | None = None
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        """兼容加身份字段之前写下的旧日志：缺什么标 unknown，不凭空编造。"""
        data = dict(data)
        data.setdefault("run_id", UNKNOWN)
        data.setdefault("actor", UNKNOWN)
        data.setdefault("caused_by", None)
        return cls(**data)
