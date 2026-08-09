# Loopbase

**面向金融的开放智能体框架——工具即能力，证据即信任。**

让循环保持运转，让证据保持诚实。

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14+-blue)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](packages/kernel/pyproject.toml)
[![Status](https://img.shields.io/badge/status-Stage%201-yellow)](ROADMAP.md)

[路线图](ROADMAP.md) · [工程结构](STRUCTURE.md) · [English](README.md)

Loopbase 是一个面向金融领域的开源 Agent Harness：以零强制依赖、与厂商无关的循环内核
（`packages/kernel`）为基座，加上金融工具层（`packages/finance`）。它让 agent 的"思考—行动"
循环可审查、可恢复：结构化工具、与厂商无关的模型接入、append-only 的证据日志。内核保持
领域无关，旅行等其他领域以后可以随时接入，无需改动内核。

## 为什么需要 Loopbase

一个 agent 可以在一次会话里完成一个任务。但长时间运行的工作更难：目标会漂移、工具会在中途失败、证据会过期、模型可能因为一个坏的工具结果无限空转。聊天记忆和一段裸的 while 循环，不足以治理这些。

Loopbase 把持久的循环状态收在一个紧凑的层里：

```
用户目标
   │
   ▼
Loopbase：循环 + 工具注册表 + 证据日志
   │
   ├─ 模型想调工具？──▶ 执行 → 追加证据 → 继续
   │
   └─ 模型给出回答？──▶ 停止，保留对话与证据
   │
   ▼
下一轮（目标、配额、恢复、交接 —— 后续阶段）
```

一个有用的心智模型：**Loopbase 是循环的"运行记录"，不是循环的"大脑"。** 模型负责提议；内核负责执行工具、记录证据、决定循环何时可以停止。

## Loopbase 是什么 / 不是什么

Loopbase 适用于：

- 事后必须能被审计的多步 agent 任务；
- 必须能在不同模型/API 间平滑切换的工具调用循环；
- 以后需要目标、配额、恢复、交接能力的长期工作。

Loopbase 不是：

- 多 agent 图编排引擎——只留接口，Stage 8，尚未启动；
- UI 或 iOS 客户端——那些是这个内核的下游使用方；
- 托管服务或租户化服务；
- 金融应用或荐股产品——Loopbase 是底下的 harness，领域逻辑在 `packages/finance`，内核保持领域无关。

## 快速体验

环境要求：Python 3.14+ 和 [uv](https://docs.astral.sh/uv/)（或任何 Python 3.14 环境）。

```bash
git clone https://github.com/anxiong2025/Loopbase.git
cd Loopbase
uv sync
```

跑真实模型 demo（每轮打印完整请求/响应，需要 API key）：

```bash
cp .env.example .env   # 填入 API key / base_url / model
uv run examples/stage2_finance/demo.py
```

跑单元测试：

```bash
uv run --project packages/kernel --extra dev pytest packages/kernel/tests/unit -q
```

## 当前能力

| 能力 | 做什么 |
|---|---|
| ReAct 循环 | 模型 ↔ 工具反复轮转，直到模型给出回答或达到最大轮数 |
| 工具注册表 | JSON Schema 工具定义，支持运行时注册；错误会回填给模型 |
| 模型客户端 | 厂商无关的 `ModelClient` 协议；已实现 OpenAI/DeepSeek 与 Anthropic 两种方言 |
| 证据日志 | append-only JSONL，每条状态转移带 schema 版本、时间戳、唯一 id |
| 配置 | 极简 `.env` 加载；密钥不进代码 |

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0–1 | 最小 ReAct 循环、工具注册表、模型方言、证据日志 | ✅ 已完成（v0.1.0） |
| 2 | 结构化目标与任务管理 | 下一步 |
| 3 | 并行与顺序依赖的多工具编排 | 计划中 |
| 4 | 状态持久化、检查点恢复、来源标记 | 计划中 |
| 5 | 上下文预算、压缩、记忆分层 | 计划中 |
| 6 | 配额感知生命周期与恢复 | 计划中 |
| 7 | 可验证交接 | 计划中 |
| 8 | 图编排（内核之外） | 未启动 |

完整细节：[ROADMAP.md](ROADMAP.md)。

## 设计原则

每条原则都必须能被一个具体测试证伪：

1. 核心循环零强制运行时依赖——`kernel/` 只用标准库就能跑通最小闭环。
2. 任意时刻可安全落盘、可完整恢复。
3. 每次状态转移都有可审计证据。
4. 核心循环、模型后端、工具、领域逻辑四者解耦。
5. 涉及真实世界后果的动作必须经过策略层。

## 仓库布局

```
packages/kernel/   开源交付物：领域无关，只用标准库
packages/travel/   旅行领域（第一个使用方，后续）
apps/              api / web / ios 客户端（下游使用方，后续）
examples/          可运行的阶段 demo
schemas/           语言中立的 JSON Schema（唯一真相源）
```

完整约定见 [STRUCTURE.md](STRUCTURE.md)。

## 当前状态

v0.1.0 —— 早期但可用的单 agent 循环内核。Stage 0–1 已完成：最小 ReAct 循环、运行时工具注册、OpenAI/DeepSeek + Anthropic 方言、证据日志、8 个通过的单元测试、一个免 key 的 demo。它不是完整的 agent 平台，不是图引擎，也不是自主生产控制器。

## 参与贡献

Loopbase 还很早期。最有价值的反馈来自真实的长时间运行 agent 项目：循环在哪里帮到了你、在哪里显得笨重、哪些控制项从视野里消失了。bug 和功能请求请开 issue；小而公开安全的改进欢迎提 PR。

## 许可证

Apache-2.0。见 [LICENSE](LICENSE)。
