# Loopbase Travel API

把旅行攻略 Agent Runtime（`packages/travel` + 通用内核）暴露成 HTTP 服务。

## 本地启动

```bash
uv sync
uv run --package api uvicorn api.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 可以直接调试后端接口。

## Docker 运行

```bash
docker build -f apps/api/Dockerfile -t loopbase-api .
docker run -p 8000:8000 --env-file .env loopbase-api
```

`--env-file .env` 会把模型 API key、base URL 和模型名称注入容器。

## 接口

- `GET /` 浏览器页面
- `GET /health` 健康检查
- `POST /run` 接收一句自然语言，自动完成 Goal Intake、任务规划和串行执行
- `POST /analyze` 接收结构化目标，返回目标记录、最终分析、轮数、停止原因和执行过的工具
- `POST /plan` 接收同一结构化目标，由 LLM 提议任务，再返回 Runtime 校验后的 `task-plan/v1`
- `POST /plan-and-execute` 先规划任务，再由 `TaskExecutor` 按依赖将任务逐个交给 ReActLoop 执行

`/plan` 请求中设置 `"include_raw_response": true`，可以同时查看尚未经过
Planner 解析的模型原文、模型供应商完整响应，以及 Runtime 处理后的 TaskPlan。

最简单的产品入口：

```json
{
  "prompt": "深圳旅行攻略3天2夜，预算5000"
}
```

信息足够时 `/run` 会继续规划并执行；缺少目的地等阻塞信息时返回
`needs_clarification` 和最多三个追问。

`/analyze` 请求示例：

```json
{
  "goal": {
    "objective": "制定从深圳出发的北京三日游攻略",
    "success_criteria": ["给出三天每日安排", "列出预算构成"],
    "constraints": ["总预算不超过3000元", "不得编造实时价格"],
    "context": {"origin": "深圳", "destination": "北京", "days": 3, "budget": 3000}
  },
  "max_turns": 5
}
```

## 注意

- `/analyze` 和 `/plan-and-execute` 会真实调用配置的模型；天气和地点资料工具会请求公开数据源。
- 当前没有真实机票、火车票和酒店报价工具，Agent 必须把这些金额标成待查询或明确估算。
