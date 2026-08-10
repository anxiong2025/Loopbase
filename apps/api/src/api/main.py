"""Loopbase Travel API：把旅行攻略 Agent Runtime 暴露成 HTTP 接口。

本地启动：
    uv sync
    uv run --package api uvicorn api.main:app --reload --port 8000

Docker：
    docker build -f apps/api/Dockerfile -t loopbase-api .
    docker run -p 8000:8000 --env-file .env loopbase-api

浏览器打开 http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from loopbase import (
    Goal,
    GoalIntake,
    IntakeGenerationError,
    IntakeStatus,
    JsonlEvidenceLog,
    OpenAICompatibleClient,
    PlanGenerationError,
    ReActLoop,
    TaskExecutor,
    TaskPlanner,
    ToolRegistry,
)
from loopbase.config import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator
from travel_agent import build_system_prompt
from travel_agent.tools import register_all

load_dotenv()  # 本地读取根目录 .env；容器里用环境变量传入

app = FastAPI(title="Loopbase Travel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("LOOPBASE_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = build_system_prompt()

_INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text(
    encoding="utf-8"
)


class _TTLCache:
    """极简内存 TTL 缓存，避免重复运行相同旅行目标。"""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        cached = self._store.get(key)
        if cached is None or time.monotonic() - cached[0] >= self._ttl:
            return None
        return cached[1]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

    def get_or_set(self, key: str, compute: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value)
        return value


_report_cache = _TTLCache(ttl_seconds=6 * 3600)


class GoalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    schema_version: Literal["goal/v1"] = "goal/v1"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1)
    objective: str = Field(min_length=1)
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time, ge=0)

    def to_domain(self) -> Goal:
        return Goal.from_dict(self.model_dump())

    @model_validator(mode="after")
    def validate_goal_contract(self) -> Self:
        self.to_domain()
        return self


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: GoalRequest
    max_turns: int = Field(default=5, ge=1, le=20)
    force_refresh: bool = False


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: GoalRequest
    max_tasks: int = Field(default=12, ge=1, le=30)
    include_raw_response: bool = False


class PlanAndExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: GoalRequest
    max_tasks: int = Field(default=12, ge=1, le=30)
    max_turns: int = Field(default=5, ge=1, le=20)
    include_raw_response: bool = False


class PromptRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    max_questions: int = Field(default=3, ge=1, le=5)
    max_tasks: int = Field(default=12, ge=1, le=30)
    max_turns: int = Field(default=5, ge=1, le=20)
    include_raw_response: bool = False


def _build_client() -> OpenAICompatibleClient:
    api_key = (
        os.environ.get("LOOPBASE_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("MOONSHOT_API_KEY")
    )
    if not api_key:
        raise RuntimeError("未找到 API key，请配置 .env 或环境变量（参考 .env.example）")
    return OpenAICompatibleClient(
        api_key=api_key,
        base_url=os.environ.get("LOOPBASE_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.environ.get("LOOPBASE_MODEL", "deepseek-chat"),
    )


def _build_loop(
    max_turns: int,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> ReActLoop:
    """按当前配置构建一次独立的 agent 循环（每次请求新注册工具，避免共享状态）。"""
    tools = ToolRegistry()
    register_all(tools)

    evidence_dir = Path(os.environ.get("LOOPBASE_EVIDENCE_DIR", "/tmp"))
    return ReActLoop(
        client=_build_client(),
        tools=tools,
        max_turns=max_turns,
        system_prompt=SYSTEM_PROMPT,
        evidence_log=JsonlEvidenceLog(evidence_dir / "evidence_api.jsonl"),
        on_event=on_event,
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    """跑一轮完整 agent 循环，返回最终分析。"""
    try:
        loop = _build_loop(request.max_turns)
        result = loop.run(request.goal.to_domain())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "goal": result.goal.as_dict(),
        "final_answer": result.final_answer,
        "turns": result.turns,
        "stopped_by": result.stopped_by,
        "tool_calls_executed": result.tool_calls_executed,
    }


@app.post("/plan")
def plan_tasks(request: PlanRequest) -> dict:
    """让模型提议任务清单，再由 Runtime 生成并校验 TaskPlan。"""
    try:
        planner = TaskPlanner(client=_build_client(), max_tasks=request.max_tasks)
        result = planner.plan_with_trace(request.goal.to_domain())
    except PlanGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if request.include_raw_response:
        return {
            "raw_model_response": result.raw_response_as_dict(),
            "task_plan": result.plan.as_dict(),
        }
    return result.plan.as_dict()


@app.post("/plan-and-execute")
def plan_and_execute(request: PlanAndExecuteRequest) -> dict:
    """先由 LLM 规划，再按依赖将每个任务交给 ReActLoop 串行执行。"""
    goal = request.goal.to_domain()
    try:
        planning = TaskPlanner(
            client=_build_client(),
            max_tasks=request.max_tasks,
        ).plan_with_trace(goal)
        execution = TaskExecutor(
            runner=_build_loop(request.max_turns)
        ).execute(goal, planning.plan)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = {"execution": execution.as_dict()}
    if request.include_raw_response:
        response["raw_planner_response"] = planning.raw_response_as_dict()
    return response


@app.post("/run")
def run_prompt(request: PromptRunRequest) -> dict:
    """一句自然语言完成目标整理、任务规划和串行执行。"""
    try:
        client = _build_client()
        intake = GoalIntake(
            client=client,
            max_questions=request.max_questions,
        ).intake(request.prompt)
        if intake.status is IntakeStatus.NEEDS_CLARIFICATION:
            response = intake.as_dict()
            if request.include_raw_response:
                response["raw_intake_response"] = intake.raw_response_as_dict()
            return response

        if intake.goal is None:  # pragma: no cover - guarded by IntakeStatus contract
            raise RuntimeError("goal intake returned ready without a goal")
        planning = TaskPlanner(
            client=client,
            max_tasks=request.max_tasks,
        ).plan_with_trace(intake.goal)
        execution = TaskExecutor(
            runner=_build_loop(request.max_turns)
        ).execute(intake.goal, planning.plan)
    except (IntakeGenerationError, PlanGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = {
        "status": execution.status.value,
        "intake": intake.as_dict(),
        "execution": execution.as_dict(),
    }
    if request.include_raw_response:
        response["raw_intake_response"] = intake.raw_response_as_dict()
        response["raw_planner_response"] = planning.raw_response_as_dict()
    return response


@app.get("/config")
def config() -> dict:
    """给前端展示当前分析配置（模型、可用工具），不含密钥。"""
    tools = ToolRegistry()
    register_all(tools)
    return {
        "model": os.environ.get("LOOPBASE_MODEL", "deepseek-chat"),
        "base_url": os.environ.get("LOOPBASE_BASE_URL", "https://api.deepseek.com/v1"),
        "tools": tools.names(),
        "default_max_turns": 5,
    }


@app.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    """SSE：把 agent 循环的每一步（轮次/工具调用/结果）实时推给前端。

    同一个旅行目标缓存 6 小时，重复请求不重新跑一遍真实的 LLM + 工具调用。
    force_refresh 可以绕过缓存强制重新生成。
    """
    goal = request.goal.to_domain()
    cache_key = json.dumps(
        {"goal": goal.model_payload(), "max_turns": request.max_turns},
        ensure_ascii=False,
        sort_keys=True,
    )

    async def event_source():
        if not request.force_refresh:
            cached = _report_cache.get(cache_key)
            if cached is not None:
                cached_payload = {
                    **cached,
                    "goal": goal.as_dict(),
                    "cache_hit": True,
                }
                yield f"data: {json.dumps(cached_payload, ensure_ascii=False)}\n\n"
                return

        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(kind: str, payload: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, {"kind": kind, **payload})

        def worker() -> None:
            try:
                agent_loop = _build_loop(request.max_turns, on_event=emit)
                result = agent_loop.run(goal)
                done_payload = {
                    "goal": result.goal.as_dict(),
                    "final_answer": result.final_answer,
                    "turns": result.turns,
                    "stopped_by": result.stopped_by,
                    "tool_calls_executed": result.tool_calls_executed,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "cache_hit": False,
                }
                if result.final_answer:  # 只缓存真正给出答案的结果，半途而废的不缓存
                    _report_cache.set(cache_key, {"kind": "done", **done_payload})
                emit("done", done_payload)
            except Exception as exc:  # noqa: BLE001 — 任何错误都要传给前端，不能让流挂起
                emit("error", {"message": str(exc)})

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item["kind"] in ("done", "error"):
                break

    return StreamingResponse(event_source(), media_type="text/event-stream")
