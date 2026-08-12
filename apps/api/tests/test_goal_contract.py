"""HTTP boundary tests for the Stage 2 structured-goal contract."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from loopbase import (
    Goal,
    JsonlEvidenceLog,
    Message,
    ModelResponse,
    RunResult,
    replay_run,
)

from api import main
from api.main import (
    AnalyzeRequest,
    PlanAndExecuteRequest,
    PlanRequest,
    PromptRunRequest,
    app,
)


def test_analyze_request_builds_a_domain_goal() -> None:
    request = AnalyzeRequest.model_validate(
        {
            "goal": {
                "objective": "制定北京三日游攻略",
                "success_criteria": ["给出三天每日安排"],
                "constraints": ["不得编造实时价格"],
                "context": {"destination": "北京", "days": 3},
            },
            "max_turns": 5,
        }
    )

    goal = request.goal.to_domain()

    assert goal.schema_version == "goal/v1"
    assert goal.objective == "制定北京三日游攻略"
    assert goal.success_criteria == ("给出三天每日安排",)
    assert goal.context == {"destination": "北京", "days": 3}


@pytest.mark.parametrize("payload", [{}, {"question": "旧字符串入口"}])
def test_analyze_request_rejects_missing_or_legacy_goal(payload) -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(payload)


def test_plan_request_requires_a_structured_goal() -> None:
    request = PlanRequest.model_validate(
        {"goal": {"objective": "制定北京三日游计划"}, "max_tasks": 8}
    )

    assert request.goal.to_domain().objective == "制定北京三日游计划"
    assert request.max_tasks == 8
    assert any(route.path == "/plan" for route in app.routes)


def test_plan_endpoint_returns_a_runtime_validated_plan(monkeypatch) -> None:
    class Client:
        def complete(self, messages, tools):
            assert tools == []
            content = json.dumps(
                {
                    "tasks": [
                        {
                            "key": "research",
                            "title": "查询信息",
                            "description": "收集交通、住宿和景点信息",
                            "depends_on": [],
                            "completion_criteria": ["信息具有明确来源"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
            return ModelResponse(
                message=Message(role="assistant", content=content),
                finish_reason="stop",
            )

    monkeypatch.setattr(main, "_build_client", lambda: Client())
    request = PlanRequest.model_validate(
        {"goal": {"objective": "制定北京三日游计划"}}
    )

    response = main.plan_tasks(request)

    assert response["schema_version"] == "task-plan/v1"
    assert response["goal_id"] == request.goal.id
    assert response["tasks"][0]["status"] == "pending"


def test_plan_endpoint_can_include_raw_model_response(monkeypatch) -> None:
    raw_provider_response = {"id": "chatcmpl-test", "choices": []}

    class Client:
        def complete(self, messages, tools):
            content = json.dumps(
                {
                    "tasks": [
                        {
                            "key": "research",
                            "title": "查询信息",
                            "description": "收集交通信息",
                            "depends_on": [],
                            "completion_criteria": ["得到交通信息"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
            return ModelResponse(
                message=Message(role="assistant", content=content),
                finish_reason="stop",
                usage={"total_tokens": 42},
                raw=raw_provider_response,
            )

    monkeypatch.setattr(main, "_build_client", lambda: Client())
    request = PlanRequest.model_validate(
        {
            "goal": {"objective": "制定北京三日游计划"},
            "include_raw_response": True,
        }
    )

    response = main.plan_tasks(request)

    assert json.loads(response["raw_model_response"]["content"])["tasks"][0][
        "key"
    ] == "research"
    assert response["raw_model_response"]["finish_reason"] == "stop"
    assert response["raw_model_response"]["usage"] == {"total_tokens": 42}
    assert response["raw_model_response"]["provider_response"] == raw_provider_response
    assert response["task_plan"]["tasks"][0]["status"] == "pending"


def test_plan_and_execute_endpoint_runs_the_validated_plan(monkeypatch) -> None:
    class PlannerClient:
        def complete(self, messages, tools):
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=json.dumps(
                        {
                            "tasks": [
                                {
                                    "key": "research",
                                    "title": "查询信息",
                                    "description": "收集完成目标所需的信息",
                                    "depends_on": [],
                                    "completion_criteria": ["得到查询结果"],
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                ),
                finish_reason="stop",
            )

    class Runner:
        def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
            return RunResult(
                final_answer="任务执行结果",
                turns=2,
                goal=goal,
                tool_calls_executed=["fake_tool"],
                stopped_by="model",
            )

    monkeypatch.setattr(main, "_build_client", lambda: PlannerClient())
    monkeypatch.setattr(
        main, "_build_loop", lambda max_turns, **kwargs: Runner()
    )
    request = PlanAndExecuteRequest.model_validate(
        {
            "goal": {"objective": "完成一个需要工具的目标"},
            "max_tasks": 4,
            "max_turns": 3,
            "include_raw_response": True,
        }
    )

    response = main.plan_and_execute(request)

    assert response["execution"]["status"] == "completed"
    assert response["execution"]["final_answer"] == "任务执行结果"
    assert response["execution"]["task_plan"]["tasks"][0]["status"] == "completed"
    assert response["execution"]["task_records"][0]["tool_calls_executed"] == [
        "fake_tool"
    ]
    assert "raw_planner_response" in response
    assert any(route.path == "/plan-and-execute" for route in app.routes)


def test_api_registers_only_travel_domain_tools() -> None:
    response = main.config()

    assert response["tools"] == [
        "get_weather_forecast",
        "search_travel_places",
        "calculate_location_distance",
        "calculate_trip_budget",
    ]


def test_run_endpoint_accepts_one_natural_language_prompt(monkeypatch) -> None:
    class Client:
        calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                content = {
                    "objective": "制定深圳3天2夜旅行攻略",
                    "success_criteria": ["给出三天每日行程", "列出预算明细"],
                    "constraints": ["总预算不超过5000元"],
                    "context": {
                        "destination_city": "深圳",
                        "days": 3,
                        "nights": 2,
                        "budget": 5000,
                    },
                    "missing_information": [],
                    "questions": [],
                }
            else:
                content = {
                    "tasks": [
                        {
                            "key": "guide",
                            "title": "制定旅行攻略",
                            "description": "制定深圳三天每日安排并核对预算",
                            "depends_on": [],
                            "completion_criteria": ["输出三天行程和预算"],
                        }
                    ]
                }
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=json.dumps(content, ensure_ascii=False),
                ),
                finish_reason="stop",
            )

    class Runner:
        def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
            return RunResult(
                final_answer="深圳三日攻略",
                turns=2,
                goal=goal,
                stopped_by="model",
            )

    client = Client()
    monkeypatch.setattr(main, "_build_client", lambda: client)
    monkeypatch.setattr(
        main, "_build_loop", lambda max_turns, **kwargs: Runner()
    )
    request = PromptRunRequest.model_validate(
        {"prompt": "深圳旅行攻略3天2夜，预算5000"}
    )

    response = main.run_prompt(request)

    assert response["status"] == "completed"
    assert response["intake"]["goal"]["context"]["destination_city"] == "深圳"
    assert response["execution"]["final_answer"] == "深圳三日攻略"
    assert client.calls == 2
    assert any(route.path == "/run" for route in app.routes)


def test_run_endpoint_returns_clarification_without_planning(monkeypatch) -> None:
    class Client:
        def complete(self, messages, tools):
            content = {
                "objective": "制定3天2夜旅行攻略",
                "success_criteria": ["给出每日行程"],
                "constraints": [],
                "context": {"days": 3, "nights": 2},
                "missing_information": ["destination_city"],
                "questions": ["你想去哪个城市？"],
            }
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=json.dumps(content, ensure_ascii=False),
                ),
                finish_reason="stop",
            )

    monkeypatch.setattr(main, "_build_client", lambda: Client())
    request = PromptRunRequest.model_validate({"prompt": "帮我安排3天2夜旅行"})

    response = main.run_prompt(request)

    assert response["status"] == "needs_clarification"
    assert response["goal"] is None
    assert response["questions"] == ["你想去哪个城市？"]


def test_run_endpoint_writes_one_auditable_run_to_the_evidence_log(
    monkeypatch, tmp_path
) -> None:
    """一次 /run 请求在日志里必须是**一条**运行，intake/planner/executor 共享 run_id。

    分别 new 各自的 log 时每个组件写自己的 run_id，事后没法把一次会话还原出来——
    这条测试守的就是那个接线。
    """

    class Client:
        calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            content = (
                {
                    "objective": "制定深圳3天攻略",
                    "success_criteria": ["给出三天每日行程"],
                    "constraints": [],
                    "context": {"destination_city": "深圳", "days": 3},
                    "missing_information": [],
                    "questions": [],
                }
                if self.calls == 1
                else {
                    "tasks": [
                        {
                            "key": "guide",
                            "title": "制定旅行攻略",
                            "description": "制定深圳三天每日安排",
                            "depends_on": [],
                            "completion_criteria": ["输出三天行程"],
                        }
                    ]
                }
            )
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=json.dumps(content, ensure_ascii=False),
                ),
                finish_reason="stop",
            )

    class Runner:
        def run(self, goal: Goal, *, caused_by: str | None = None) -> RunResult:
            return RunResult(
                final_answer="深圳三日攻略",
                turns=1,
                goal=goal,
                stopped_by="model",
            )

    monkeypatch.setenv("LOOPBASE_EVIDENCE_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_build_client", lambda: Client())
    monkeypatch.setattr(main, "_build_loop", lambda max_turns, **kwargs: Runner())

    main.run_prompt(PromptRunRequest.model_validate({"prompt": "深圳旅行攻略3天"}))

    records = JsonlEvidenceLog(tmp_path / "evidence_api.jsonl").read_all()
    assert len({record.run_id for record in records}) == 1
    assert [record.kind for record in records] == [
        "intake.start",
        "intake.completed",
        "plan.start",
        "plan.created",
        "execution.start",
        "task.started",
        "task.completed",
        "execution.finished",
    ]
    assert {record.actor for record in records} == {"intake", "planner", "executor"}

    # 只凭日志复算，得出跟接口返回一样的结论
    replayed = replay_run(records)
    assert replayed.finished is True
    assert list(replayed.outputs.values()) == ["深圳三日攻略"]
