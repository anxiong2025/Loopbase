"""Stage 4 埋点：只看事件日志能不能审出一次会话做了什么。

这些测试守的是设计原则第 3 条「每个状态转移都有可审计证据」。之前这条只对
ReAct 内层循环成立，intake / planner / executor 三个真正决定 agent 干了什么的
组件一条都不写。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from loopbase import (
    EvidenceLog,
    Goal,
    GoalIntake,
    MemoryStore,
    Message,
    ModelResponse,
    PlanGenerationError,
    RunResult,
    TaskExecutor,
    TaskPlan,
    TaskPlanner,
    replay_run,
)


@dataclass
class OneShotClient:
    content: str

    def complete(self, messages, tools):
        return ModelResponse(
            message=Message(role="assistant", content=self.content),
            finish_reason="stop",
        )


@dataclass
class SuccessfulRunner:
    seen_caused_by: list[str | None] = field(default_factory=list)

    def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
        self.seen_caused_by.append(caused_by)
        return RunResult(
            final_answer=f"已完成：{goal.objective.splitlines()[0]}",
            turns=1,
            goal=goal,
            stopped_by="model",
        )


def _log() -> EvidenceLog:
    return EvidenceLog(MemoryStore(), run_id="run_a")


def _goal() -> Goal:
    return Goal(objective="去东京玩三天", id="goal_trip", created_at=1.0)


def _plan(goal_id: str = "goal_trip") -> TaskPlan:
    from loopbase import Task

    return TaskPlan(
        id="plan_trip",
        goal_id=goal_id,
        tasks=(
            Task(
                id="research",
                goal_id=goal_id,
                title="收集信息",
                description="收集信息",
                created_at=1.0,
                updated_at=1.0,
            ),
            Task(
                id="itinerary",
                goal_id=goal_id,
                title="规划行程",
                description="规划行程",
                depends_on=("research",),
                created_at=1.0,
                updated_at=1.0,
            ),
        ),
        created_at=1.0,
    )


# ------------------------------------------------------------------ intake


def test_intake_records_the_prompt_and_the_resulting_goal() -> None:
    log = _log()
    client = OneShotClient(
        json.dumps(
            {
                "objective": "制定东京3天攻略",
                "success_criteria": ["给出三天每日行程"],
                "constraints": [],
                "context": {"destination_city": "东京", "days": 3},
                "missing_information": [],
                "questions": [],
            }
        )
    )

    GoalIntake(client=client, evidence_log=log).intake("我想去东京玩三天")

    records = log.read_run()
    assert [r.kind for r in records] == ["intake.start", "intake.completed"]
    assert all(r.actor == "intake" for r in records)
    assert records[0].payload["prompt"] == "我想去东京玩三天"
    assert records[1].payload["result"]["goal"]["objective"] == "制定东京3天攻略"
    assert records[1].caused_by == records[0].id


def test_intake_records_a_clarification_stop_distinctly() -> None:
    log = _log()
    client = OneShotClient(
        json.dumps(
            {
                "objective": "在预算内制定旅行攻略",
                "success_criteria": ["给出每日行程"],
                "constraints": [],
                "context": {},
                "missing_information": ["destination_city"],
                "questions": ["你想去哪个城市？"],
            }
        )
    )

    GoalIntake(client=client, evidence_log=log).intake("帮我安排个旅行")

    assert [r.kind for r in log.read_run()] == [
        "intake.start",
        "intake.needs_clarification",
    ]


def test_intake_records_the_failure_instead_of_going_silent() -> None:
    log = _log()
    try:
        GoalIntake(client=OneShotClient("not json"), evidence_log=log).intake("x")
    except Exception:  # noqa: BLE001 - 这里只关心日志写没写
        pass

    records = log.read_run()
    assert [r.kind for r in records] == ["intake.start", "intake.failed"]
    assert records[1].payload["error_type"] == "IntakeGenerationError"


# ----------------------------------------------------------------- planner


def test_planner_records_the_validated_plan() -> None:
    log = _log()
    client = OneShotClient(
        json.dumps(
            {
                "tasks": [
                    {
                        "key": "research",
                        "title": "收集信息",
                        "description": "收集东京信息",
                        "depends_on": [],
                        "completion_criteria": ["有信息清单"],
                    }
                ]
            }
        )
    )

    TaskPlanner(client=client, evidence_log=log).plan(_goal())

    records = log.read_run()
    assert [r.kind for r in records] == ["plan.start", "plan.created"]
    assert all(r.actor == "planner" for r in records)
    assert records[1].payload["task_plan"]["tasks"][0]["title"] == "收集信息"
    assert records[1].caused_by == records[0].id


def test_planner_records_the_failure() -> None:
    log = _log()
    try:
        TaskPlanner(client=OneShotClient("{}"), evidence_log=log).plan(_goal())
    except PlanGenerationError:
        pass

    assert [r.kind for r in log.read_run()] == ["plan.start", "plan.failed"]


# ---------------------------------------------------------------- executor


def test_executor_records_the_whole_task_lifecycle() -> None:
    log = _log()
    runner = SuccessfulRunner()

    TaskExecutor(runner=runner, evidence_log=log).execute(_goal(), _plan())

    records = log.read_run()
    assert [r.kind for r in records] == [
        "execution.start",
        "task.started",
        "task.completed",
        "task.started",
        "task.completed",
        "execution.finished",
    ]
    assert all(r.actor == "executor" for r in records)


def test_executor_hands_its_event_id_to_the_worker() -> None:
    """任务委派给 ReAct 循环之后，因果链不能断在组件边界上。"""
    log = _log()
    runner = SuccessfulRunner()

    TaskExecutor(runner=runner, evidence_log=log).execute(_goal(), _plan())

    started = [r for r in log.read_run() if r.kind == "task.started"]
    assert runner.seen_caused_by == [r.id for r in started]


def test_executor_records_failure_and_the_blocked_dependents() -> None:
    class BrokenRunner:
        def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
            raise RuntimeError("tool unavailable")

    log = _log()
    TaskExecutor(runner=BrokenRunner(), evidence_log=log).execute(_goal(), _plan())

    records = log.read_run()
    kinds = [r.kind for r in records]
    assert kinds == [
        "execution.start",
        "task.started",
        "task.failed",
        "task.blocked",
        "execution.finished",
    ]
    blocked = next(r for r in records if r.kind == "task.blocked")
    assert blocked.payload["task_id"] == "itinerary"
    assert blocked.payload["blocked_by"] == ["research"]


def test_the_log_alone_reconstructs_the_execution() -> None:
    """审计标准：不看代码、不看内存，只凭日志得出同样的结论。"""
    log = _log()
    result = TaskExecutor(runner=SuccessfulRunner(), evidence_log=log).execute(
        _goal(), _plan()
    )

    replayed = replay_run(log.read_run())

    assert replayed.task_plan.as_dict() == result.task_plan.as_dict()
    assert replayed.outputs == {
        "research": "已完成：收集信息",
        "itinerary": "已完成：规划行程",
    }
    assert replayed.finished is True
