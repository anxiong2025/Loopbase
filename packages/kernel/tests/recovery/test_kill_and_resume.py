"""Stage 4 完成标准：跑到一半 kill 进程，重启后正确接着跑。

这里用真的 SIGKILL 打一个子进程，不是抛异常模拟——只有真被打死，才能同时验证
两件事：JSONL 的 fsync 让最后几条事件没丢，以及重建出来的状态确实只来自磁盘上
的日志，不依赖任何进程内内存。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import loopbase
from loopbase import (
    ExecutionStatus,
    Goal,
    JsonlEvidenceLog,
    RunResult,
    TaskStatus,
    TaskExecutor,
    replay_run,
)

WORKER = Path(__file__).parent / "crashing_worker.py"
KERNEL_SRC = Path(loopbase.__file__).resolve().parents[1]


class WorkingRunner:
    """重启之后接手的正常 worker，顺便记下它到底又跑了哪些任务。"""

    def __init__(self) -> None:
        self.goal_ids: list[str] = []
        self.goals: list[Goal] = []

    def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
        self.goal_ids.append(goal.id)
        self.goals.append(goal)
        return RunResult(
            final_answer=f"已完成：{goal.objective.splitlines()[0]}",
            turns=1,
            goal=goal,
            stopped_by="model",
        )


def _kill_mid_plan(log_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(KERNEL_SRC), env.get("PYTHONPATH", "")])
    )
    completed = subprocess.run(
        [sys.executable, str(WORKER), str(log_path), "run_crashed"],
        env=env,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == -signal.SIGKILL, (
        f"worker exited {completed.returncode}, stderr={completed.stderr.decode()}"
    )


def test_kill_dash_nine_mid_plan_then_resume_from_the_log(tmp_path) -> None:
    log_path = tmp_path / "evidence.jsonl"
    _kill_mid_plan(log_path)

    # 只从磁盘读，进程内没有任何残留状态
    replayed = replay_run(JsonlEvidenceLog(log_path).read_all(), run_id="run_crashed")

    assert replayed.outputs == {"research": "已完成：收集信息"}
    assert replayed.task_plan.get("research").status is TaskStatus.COMPLETED
    # 忠实回放：被打死的那一刻它确实在跑
    assert replayed.task_plan.get("itinerary").status is TaskStatus.IN_PROGRESS
    assert replayed.interrupted_task_ids == ("itinerary",)
    assert replayed.is_resumable is True

    runner = WorkingRunner()
    result = TaskExecutor(
        runner=runner,
        evidence_log=JsonlEvidenceLog(log_path, run_id="run_resumed"),
    ).resume(replayed)

    assert result.status is ExecutionStatus.COMPLETED
    assert result.final_answer == "已完成：规划行程"
    # 已完成的任务不重跑，只补上被打断的那个
    assert runner.goal_ids == ["itinerary"]
    # 上一段跑出来的结果被带过来了，没有丢
    assert [record.task_id for record in result.task_records] == [
        "research",
        "itinerary",
    ]
    # 而且是真的传给了续跑的任务，不只是留在结果对象里
    assert runner.goals[0].context["dependency_results"] == [
        {
            "task_id": "research",
            "title": "收集信息",
            "output": "已完成：收集信息",
        }
    ]


def test_the_resumed_run_is_self_contained_in_the_log(tmp_path) -> None:
    """续跑那一段单独重放也要能得出完整结论，不需要再去翻上一次运行的事件。"""
    log_path = tmp_path / "evidence.jsonl"
    _kill_mid_plan(log_path)

    replayed = replay_run(JsonlEvidenceLog(log_path).read_all(), run_id="run_crashed")
    TaskExecutor(
        runner=WorkingRunner(),
        evidence_log=JsonlEvidenceLog(log_path, run_id="run_resumed"),
    ).resume(replayed)

    after = replay_run(JsonlEvidenceLog(log_path).read_all(), run_id="run_resumed")

    assert after.finished is True
    assert after.is_resumable is False
    assert after.outputs == {
        "research": "已完成：收集信息",
        "itinerary": "已完成：规划行程",
    }
    assert all(
        task.status is TaskStatus.COMPLETED for task in after.task_plan.tasks
    )


def test_replaying_the_whole_file_defaults_to_the_latest_run(tmp_path) -> None:
    log_path = tmp_path / "evidence.jsonl"
    _kill_mid_plan(log_path)

    replayed = replay_run(JsonlEvidenceLog(log_path).read_all(), run_id="run_crashed")
    TaskExecutor(
        runner=WorkingRunner(),
        evidence_log=JsonlEvidenceLog(log_path, run_id="run_resumed"),
    ).resume(replayed)

    # 不指定 run_id 时取最后一次运行——「接着上次跑」的默认意图
    assert replay_run(JsonlEvidenceLog(log_path).read_all()).run_id == "run_resumed"
