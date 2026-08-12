"""被 kill -9 的那个进程。由 test_kill_and_resume.py 拉起来，不是测试本身。

它跑一个两步计划，第一步正常完成，第二步开跑之后立刻给自己发 SIGKILL——
SIGKILL 抓不到、也没有 atexit，跟真的被运维/OOM killer 干掉一样。
"""

from __future__ import annotations

import os
import signal
import sys

from loopbase import (
    Goal,
    JsonlEvidenceLog,
    RunResult,
    Task,
    TaskExecutor,
    TaskPlan,
)

GOAL_ID = "goal_trip"


def build_goal() -> Goal:
    return Goal(
        objective="去东京玩三天",
        success_criteria=["有每日行程"],
        id=GOAL_ID,
        created_at=1.0,
    )


def build_plan() -> TaskPlan:
    def task(task_id: str, title: str, depends_on: tuple[str, ...] = ()) -> Task:
        return Task(
            id=task_id,
            goal_id=GOAL_ID,
            title=title,
            description=f"完成{title}",
            depends_on=depends_on,
            created_at=1.0,
            updated_at=1.0,
        )

    return TaskPlan(
        id="plan_trip",
        goal_id=GOAL_ID,
        tasks=(
            task("research", "收集信息"),
            task("itinerary", "规划行程", depends_on=("research",)),
        ),
        created_at=1.0,
    )


class CrashingRunner:
    """第二个任务一开跑就把进程打死。"""

    def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
        if goal.id == "itinerary":
            os.kill(os.getpid(), signal.SIGKILL)
        return RunResult(
            final_answer=f"已完成：{goal.objective.splitlines()[0]}",
            turns=1,
            goal=goal,
            stopped_by="model",
        )


def main() -> None:
    log_path, run_id = sys.argv[1], sys.argv[2]
    executor = TaskExecutor(
        runner=CrashingRunner(),
        evidence_log=JsonlEvidenceLog(log_path, run_id=run_id),
    )
    executor.execute(build_goal(), build_plan())
    raise SystemExit("worker was supposed to be killed before finishing")


if __name__ == "__main__":
    main()
