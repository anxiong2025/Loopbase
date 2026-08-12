"""Layer 7 的单元测试：Store 契约、schema 版本校验、事件重放。"""

from __future__ import annotations

import json

import pytest

from loopbase import (
    EvidenceLog,
    EvidenceRecord,
    EvidenceSchemaMismatch,
    JsonlEvidenceLog,
    JsonlStore,
    MemoryStore,
    ReplayError,
    TaskStatus,
    replay_run,
)
from loopbase.observability import Actor, EventKind


def _goal_dict(goal_id: str = "goal_trip") -> dict:
    return {
        "schema_version": "goal/v1",
        "id": goal_id,
        "objective": "去东京玩三天",
        "success_criteria": ["有每日行程"],
        "constraints": [],
        "context": {},
        "created_at": 1.0,
    }


def _task_dict(task_id: str, depends_on: list[str] | None = None) -> dict:
    return {
        "id": task_id,
        "goal_id": "goal_trip",
        "title": f"任务 {task_id}",
        "description": f"完成 {task_id}",
        "depends_on": depends_on or [],
        "completion_criteria": [],
        "status": "pending",
        "created_at": 1.0,
        "updated_at": 1.0,
    }


def _plan_dict(*tasks: dict) -> dict:
    return {
        "schema_version": "task-plan/v1",
        "id": "plan_trip",
        "goal_id": "goal_trip",
        "tasks": list(tasks),
        "created_at": 1.0,
    }


def _record_dict(task_id: str, output: str | None, status: str = "completed") -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "output": output,
        "error": None,
        "turns": 1,
        "stopped_by": "model",
        "tool_calls_executed": [],
        "started_at": 2.0,
        "finished_at": 3.0,
    }


# ---------------------------------------------------------------- Store 契约


@pytest.mark.parametrize("store_name", ["jsonl", "memory"])
def test_store_contract_appends_and_reads_back(tmp_path, store_name) -> None:
    """一套断言跑遍所有 Store 实现——换后端不改调用方，这是 Rust 接缝的前提。"""
    store = (
        JsonlStore(tmp_path / "e.jsonl") if store_name == "jsonl" else MemoryStore()
    )
    log = EvidenceLog(store, run_id="run_a")

    log.append("a.happened", {"n": 1}, actor=Actor.LOOP)
    log.append("b.happened", {"n": 2}, actor=Actor.EXECUTOR)

    records = store.read_all()
    assert [r.kind for r in records] == ["a.happened", "b.happened"]
    assert [r.actor for r in records] == ["loop", "executor"]
    assert all(r.run_id == "run_a" for r in records)


def test_jsonl_store_rejects_unknown_event_schema_version(tmp_path) -> None:
    """读到不认识的版本要明确报错，而不是用新代码去猜旧格式。"""
    path = tmp_path / "e.jsonl"
    path.write_text(
        json.dumps(
            {
                "kind": "turn.start",
                "payload": {},
                "run_id": "r",
                "actor": "loop",
                "caused_by": None,
                "timestamp": 1.0,
                "id": "abc",
                "schema_version": "event/v2",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EvidenceSchemaMismatch, match="event/v2"):
        JsonlStore(path).read_all()


def test_read_run_isolates_one_run_out_of_a_shared_file(tmp_path) -> None:
    path = tmp_path / "e.jsonl"
    JsonlEvidenceLog(path, run_id="run_a").append("x", {})
    log_b = JsonlEvidenceLog(path, run_id="run_b")
    log_b.append("y", {})

    assert [r.kind for r in log_b.read_all()] == ["x", "y"]
    assert [r.kind for r in log_b.read_run()] == ["y"]
    assert [r.kind for r in log_b.read_run("run_a")] == ["x"]


# -------------------------------------------------------------------- 重放


def _events(*pairs: tuple[str, dict], run_id: str = "run_a") -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            kind=kind,
            payload=payload,
            run_id=run_id,
            actor=Actor.EXECUTOR,
            timestamp=float(index + 10),
        )
        for index, (kind, payload) in enumerate(pairs)
    ]


def test_replay_rebuilds_plan_state_and_outputs() -> None:
    records = _events(
        (
            EventKind.EXECUTION_START,
            {
                "goal": _goal_dict(),
                "task_plan": _plan_dict(_task_dict("a"), _task_dict("b", ["a"])),
            },
        ),
        (EventKind.TASK_STARTED, {"task_id": "a", "title": "任务 a"}),
        (
            EventKind.TASK_COMPLETED,
            {"task_id": "a", "record": _record_dict("a", "a 的产出")},
        ),
    )

    replayed = replay_run(records)

    assert replayed.run_id == "run_a"
    assert replayed.goal is not None and replayed.goal.id == "goal_trip"
    assert replayed.task_plan.get("a").status is TaskStatus.COMPLETED
    assert replayed.task_plan.get("b").status is TaskStatus.PENDING
    assert replayed.outputs == {"a": "a 的产出"}
    assert replayed.interrupted_task_ids == ()
    assert replayed.is_resumable is True


def test_replay_keeps_the_interrupted_task_visible_then_reopens_it() -> None:
    """忠实回放要看得到「死的时候它在跑」；续跑的计划才把它重开成 pending。"""
    records = _events(
        (
            EventKind.EXECUTION_START,
            {
                "goal": _goal_dict(),
                "task_plan": _plan_dict(_task_dict("a"), _task_dict("b", ["a"])),
            },
        ),
        (EventKind.TASK_STARTED, {"task_id": "a", "title": "任务 a"}),
    )

    replayed = replay_run(records)

    assert replayed.task_plan.get("a").status is TaskStatus.IN_PROGRESS
    assert replayed.interrupted_task_ids == ("a",)
    assert replayed.resumable_plan().get("a").status is TaskStatus.PENDING


def test_replay_marks_a_finished_run_as_not_resumable() -> None:
    records = _events(
        (
            EventKind.EXECUTION_START,
            {"goal": _goal_dict(), "task_plan": _plan_dict(_task_dict("a"))},
        ),
        (EventKind.TASK_STARTED, {"task_id": "a", "title": "任务 a"}),
        (
            EventKind.TASK_COMPLETED,
            {"task_id": "a", "record": _record_dict("a", "done")},
        ),
        (EventKind.EXECUTION_FINISHED, {"status": "completed"}),
    )

    replayed = replay_run(records)

    assert replayed.finished is True
    assert replayed.is_resumable is False


def test_replay_defaults_to_the_last_run_in_the_file() -> None:
    records = _events(
        (
            EventKind.EXECUTION_START,
            {"goal": _goal_dict(), "task_plan": _plan_dict(_task_dict("a"))},
        ),
        run_id="run_old",
    ) + _events(
        (
            EventKind.EXECUTION_START,
            {
                "goal": _goal_dict("goal_other"),
                "task_plan": _plan_dict(
                    {**_task_dict("z"), "goal_id": "goal_other"},
                ),
            },
        ),
        run_id="run_new",
    )
    records[-1].payload["task_plan"]["goal_id"] = "goal_other"

    replayed = replay_run(records)

    assert replayed.run_id == "run_new"
    assert replayed.goal.id == "goal_other"


def test_replay_rejects_an_empty_log() -> None:
    with pytest.raises(ReplayError, match="empty event log"):
        replay_run([])


def test_replay_rejects_a_task_event_without_a_plan() -> None:
    records = _events((EventKind.TASK_STARTED, {"task_id": "a", "title": "任务 a"}))

    with pytest.raises(ReplayError, match="never appeared in the log"):
        replay_run(records)
