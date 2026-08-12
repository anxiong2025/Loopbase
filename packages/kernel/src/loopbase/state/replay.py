"""Layer 7 — 从事件日志重建状态。

Stage 4 的完成标准是「跑到一半 kill 进程，重启后正确接着跑」。做到这件事只需要
一个前提：**状态可以完全由事件序列推导出来**，不依赖任何进程内内存。这个模块就是
那个推导过程。

它只读不写，也不认识 ``TaskExecutor``——重放出来的任务执行记录以原始 dict 形式
交回去，由执行器自己还原成它的类型。这样 ``state`` 不需要 import 执行层，
不产生循环依赖。
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..goals import Goal
from ..observability import EventKind, EvidenceRecord
from ..tasks import TaskPlan, TaskStatus


class ReplayError(ValueError):
    """事件序列无法还原成一个合法状态。"""


@dataclass(frozen=True, slots=True)
class ReplayedRun:
    """一次运行在日志里的样子。

    ``task_plan`` 是**忠实**回放：进程被杀时停在 ``in_progress`` 的任务，这里仍然
    是 ``in_progress``——审计要看到真实的最后状态。要拿去续跑请用
    ``resumable_plan()``，它才会把这些任务重开成 ``pending``。
    """

    run_id: str
    goal: Goal | None
    task_plan: TaskPlan | None
    outputs: dict[str, str]
    task_record_payloads: tuple[dict[str, Any], ...]
    interrupted_task_ids: tuple[str, ...]
    finished: bool

    @property
    def is_resumable(self) -> bool:
        """有目标、有计划、还没跑完，才谈得上续跑。"""
        return (
            self.goal is not None and self.task_plan is not None and not self.finished
        )

    def require_goal(self) -> Goal:
        if self.goal is None:
            raise ReplayError(f"run {self.run_id!r} has no goal in its event log")
        return self.goal

    def require_plan(self) -> TaskPlan:
        if self.task_plan is None:
            raise ReplayError(f"run {self.run_id!r} has no task plan in its event log")
        return self.task_plan

    def resumable_plan(self) -> TaskPlan:
        """把被中断的任务重开成 ``pending``，其余状态原样保留。

        中断的任务整个重跑，不做半个任务的续跑：ReAct 循环内部没有中途检查点，
        重放不出「工具调了一半」的状态。代价是那个任务里已经执行过的工具会再执行
        一次——当前工具都是只读查询，这是安全的；有副作用的工具要等 Layer 10
        策略层来管。

        ``in_progress`` 不能直接回到 ``pending``（见 tasks.py 的状态机），所以走
        ``in_progress → failed → pending``：中断确实是一次失败，这条路径让日志里
        看得出来它失败过又被重开，而不是凭空回到起点。
        """
        plan = self.require_plan()
        now = time.time()
        for task_id in self.interrupted_task_ids:
            plan = plan.transition(task_id, TaskStatus.FAILED, at=now)
            plan = plan.transition(task_id, TaskStatus.PENDING, at=now)
        return plan


def replay_run(
    records: Iterable[EvidenceRecord],
    *,
    run_id: str | None = None,
) -> ReplayedRun:
    """把一次运行的事件序列推导成状态。

    ``run_id`` 不传时取日志里最后出现的那次运行——「接着上次跑」是最常见的意图。
    """
    all_records = list(records)
    if run_id is None:
        if not all_records:
            raise ReplayError("cannot replay an empty event log")
        run_id = all_records[-1].run_id
    selected = [record for record in all_records if record.run_id == run_id]
    if not selected:
        raise ReplayError(f"event log contains no records for run {run_id!r}")

    goal: Goal | None = None
    plan: TaskPlan | None = None
    outputs: dict[str, str] = {}
    record_payloads: list[dict[str, Any]] = []
    open_task_ids: list[str] = []
    finished = False

    for event in selected:
        kind = event.kind
        payload = event.payload

        if kind == EventKind.INTAKE_COMPLETED:
            drafted = (payload.get("result") or {}).get("goal")
            if drafted:
                goal = Goal.from_dict(drafted)

        elif kind == EventKind.PLAN_CREATED:
            plan = TaskPlan.from_dict(payload["task_plan"])

        elif kind in (EventKind.EXECUTION_START, EventKind.EXECUTION_RESUMED):
            goal = Goal.from_dict(payload["goal"])
            plan = TaskPlan.from_dict(payload["task_plan"])
            outputs = dict(payload.get("outputs") or {})
            record_payloads = list(payload.get("task_records") or [])
            open_task_ids = []
            finished = False

        elif kind == EventKind.TASK_STARTED:
            plan = _require_plan(plan, kind).transition(
                payload["task_id"],
                TaskStatus.IN_PROGRESS,
                at=_transition_time(payload, event),
            )
            open_task_ids.append(payload["task_id"])

        elif kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
            task_id = payload["task_id"]
            status = (
                TaskStatus.COMPLETED
                if kind == EventKind.TASK_COMPLETED
                else TaskStatus.FAILED
            )
            plan = _require_plan(plan, kind).transition(
                task_id, status, at=_transition_time(payload, event)
            )
            task_record = payload["record"]
            record_payloads.append(task_record)
            if status is TaskStatus.COMPLETED and task_record.get("output") is not None:
                outputs[task_id] = task_record["output"]
            if task_id in open_task_ids:
                open_task_ids.remove(task_id)

        elif kind == EventKind.TASK_BLOCKED:
            plan = _require_plan(plan, kind).transition(
                payload["task_id"],
                TaskStatus.BLOCKED,
                at=_transition_time(payload, event),
            )

        elif kind == EventKind.EXECUTION_FINISHED:
            finished = True

    return ReplayedRun(
        run_id=run_id,
        goal=goal,
        task_plan=plan,
        outputs=outputs,
        task_record_payloads=tuple(record_payloads),
        interrupted_task_ids=tuple(open_task_ids),
        finished=finished,
    )


def _transition_time(payload: dict[str, Any], event: EvidenceRecord) -> float:
    """状态转移发生的时刻，取事件里记的那个。

    事件的 ``timestamp`` 是**写日志**的时刻，比转移本身晚一点点。用它重放会算出
    跟原来差几微秒的 ``updated_at``——那样日志就不是状态的真相源，只是它的近似。
    """
    at = payload.get("at")
    return float(at) if isinstance(at, (int, float)) else event.timestamp


def _require_plan(plan: TaskPlan | None, kind: str) -> TaskPlan:
    if plan is None:
        raise ReplayError(
            f"event {kind!r} refers to a task plan that never appeared in the log"
        )
    return plan
