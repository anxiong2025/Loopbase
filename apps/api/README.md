# Loopbase Finance API

把金融 Agent 循环（`packages/finance` + 内核）暴露成 HTTP 服务，浏览器里直接提问。

## 本地启动

```bash
uv sync
uv run --package api uvicorn api.main:app --reload --port 8000
```

打开 http://localhost:8000 ，输入问题（如“分析一下特斯拉 TSLA”）。

## Docker 运行

```bash
docker build -f apps/api/Dockerfile -t loopbase-api .
docker run -p 8000:8000 --env-file .env loopbase-api
```

`--env-file .env` 会把 `DEEPSEEK_API_KEY`、`ALPHA_VANTAGE_API_KEY` 等注入容器。

## 接口

- `GET /` 浏览器页面
- `GET /health` 健康检查
- `POST /analyze` 请求体 `{"question": "...", "max_turns": 5}`，返回最终分析、轮数、停止原因、执行过的工具

## 注意

- 每次 `/analyze` 都会真实调用 DeepSeek + Alpha Vantage，注意免费额度（Alpha Vantage 25 次/天）；
- 单用户学习用途：并发请求可能撞限流（真实调用间已加 1.1s 节流，仍建议不要并发）。
