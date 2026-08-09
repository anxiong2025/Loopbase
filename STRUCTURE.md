# Loopbase — 工程结构规范

定位与原则见 [README.md](README.md)，分阶段计划见 [ROADMAP.md](ROADMAP.md)。这份文档规定**代码放在哪、谁能
依赖谁、契约放在哪**——是硬性约定，CI 会机械校验，不靠人工自觉。

## 仓库形态：单仓多包（monorepo + workspace）

内核最终要能独立开源，但开发期内核和使用方会共同演化，拆两个仓库来回同步代价太高。所以：**现在单仓开发，
内核做成自包含的独立包**（自带 `pyproject.toml` / `README` / `LICENSE` / `CHANGELOG` / 测试），要开源时
`git subtree split -P packages/kernel` 直接切出去，切出去那天不需要任何重构。

Python 侧用 uv workspace（已在用 uv），web/iOS 各自独立的包管理，不混进 uv workspace。

## 目录树

```
loopbase/
├── README.md                    定位、边界、设计原则
├── ROADMAP.md                   Stage 0-8 计划、12 层模块全景图
├── STRUCTURE.md                 本文档
├── pyproject.toml               uv workspace 根（只声明 members + 统一工具配置，不放业务依赖）
├── uv.lock
├── .env.example
├── justfile                     统一入口：just test / just lint / just api / just web
│
├── schemas/                     ★ 语言中立的契约，唯一真相源
│   └── v1/
│       ├── event.schema.json        事件日志记录（Stage 4）
│       ├── checkpoint.schema.json   检查点（Stage 6）
│       ├── goal.schema.json         结构化目标与任务（Stage 2）
│       └── handoff.schema.json      交接记录（Stage 7）
│
├── packages/
│   ├── kernel/                  ★ 开源交付物：领域无关、零强制依赖
│   │   ├── pyproject.toml           自包含，可单独发布
│   │   ├── README.md  LICENSE  CHANGELOG.md
│   │   ├── src/loopbase/
│   │   │   ├── loop.py              层1  核心循环控制
│   │   │   ├── models/              层2  模型 I/O（多方言，天然多文件）
│   │   │   │   ├── base.py              ModelClient 协议 + 统一的请求/响应表示
│   │   │   │   ├── openai_dialect.py    OpenAI/DeepSeek 方言
│   │   │   │   └── anthropic_dialect.py Anthropic 方言
│   │   │   ├── tools/               层3  工具注册表、并发调度、沙箱边界
│   │   │   ├── goals.py             层4  目标与任务管理
│   │   │   ├── context/             层5  装配、预算、压缩、淘汰
│   │   │   ├── memory/              层6  工作/情景/语义/程序性记忆
│   │   │   ├── state/               层7  事件日志、检查点、恢复
│   │   │   ├── runtime.py           层8  配额跟踪、生命周期钩子、resume 入口
│   │   │   ├── observability.py     层9  审计日志、指标、因果链
│   │   │   ├── policy.py            层10 动作分级、不可信输入、指令来源边界
│   │   │   ├── handoff.py           层11 交接记录与验证
│   │   │   └── config.py            层12 配置、密钥、schema 版本
│   │   └── tests/
│   │       ├── unit/
│   │       ├── conformance/         ★ 契约测试：任何可替换实现都必须过
│   │       ├── recovery/            ★ kill -9、配额耗尽、resume
│   │       └── fixtures/            录制的模型响应，CI 回放不需要 API key
│   │
│   ├── travel/                  旅行领域（规划中）：工具实现、prompt、目标模板
│   │   ├── pyproject.toml
│   │   ├── src/travel_agent/
│   │   └── tests/
│   └── finance/                 金融领域（当前实现）：工具实现、prompt、目标模板
│       ├── pyproject.toml
│       ├── src/finance_agent/
│       └── tests/
│
├── apps/
│   ├── api/                     HTTP 服务：把 kernel 会话暴露给客户端（web 端先用）
│   │   ├── pyproject.toml
│   │   ├── src/travel_api/
│   │   └── tests/
│   ├── web/                     web 前端（独立 package.json，先上的客户端）
│   └── ios/                     以后的 SwiftUI（iOS + macOS 共享 target）
│
├── examples/
│   └── stage2_finance/         金融领域 demo（真实模型，打印每次请求/响应）
│
├── docs/
│   ├── adr/                     架构决策记录
│   └── function_calling_qa.md
│
└── .github/workflows/
```

**层 → 文件的晋升规则**：一层先用单个 `.py` 起步，需要超过一个文件时才提升为子包（加 `__init__.py` 目录）。
上面标成目录的（`models/` `tools/` `context/` `memory/` `state/`）是已经确定会多文件的；标成 `.py` 的先单文件，
别为了对称提前建空目录。

## 依赖方向（硬性规则，CI 用 import-linter 校验）

```
apps/api  ──→  packages/travel  ──→  packages/kernel
   └──────────────────────────────────────┘
```

- `kernel` **不许** import `travel` / `api` / 任何 web 框架 / 任何 HTTP 服务端库——这条是内核能独立开源的
  前提，也是设计原则第 1、4 条的机械保证
- `travel` 可以 import `kernel`，**不许** import `api`
- `api` 可以 import `kernel` 和 `travel`
- 领域词汇边界：`packages/kernel/` 下不允许出现 `flight` / `hotel` / `itinerary` 这类旅行词汇，CI 加一条
  grep 规则守住

**内核层内规则**（防循环依赖）：
- `policy` 和 `observability` 是横切层，任何层都可以 import 它们，它们不许 import 别的业务层
- `loop` 在最上层，可以 import 所有层
- `models` / `tools` / `state` / `context` / `memory` **不许** import `loop`

## Rust 接缝（现在只定接口，不建目录）

ROADMAP 里定位的四个候选模块，从 Stage 1 起就写成 Protocol + 纯 Python 默认实现，以后换后端是换实现、
不改接口：

| 模块 | 接口 | 默认实现 | 换 Rust 买什么 |
|---|---|---|---|
| 状态落盘引擎 | `state.Store` | 纯 Python JSONL + fsync | 崩溃安全的正确性保证 |
| Token 计数 | `context.Tokenizer` | 纯 Python 估算 | 真正的 CPU-bound 性能 |
| 工具沙箱 | `tools.Sandbox` | 子进程 + 超时 | OS 级隔离粒度 |
| 策略引擎 | `policy.Engine` | 纯 Python 分级判定 | 编译期穷尽性检查 |

要上 Rust 时新增 `packages/kernel-rs/`（maturin + PyO3），提供同样的 Protocol 实现，通过可选 extra
安装（`loopbase[rust]`），**不改任何调用方代码**。现在不建这个目录。

## 契约与代码生成

`schemas/v1/` 里的 JSON Schema 是唯一真相源，Python / TypeScript / Swift 三端都从它生成类型，不各自手写
一份对不上的定义。

- **schema 版本目录（`v1/`）跟包版本号独立**——内核发 1.3.0 时 schema 可能还是 v1；schema 破坏性变更才
  开 `v2/`，且必须保留 v1 的读取能力（Stage 4/7 的版本化要求）
- **API 契约**：`apps/api` 生成 OpenAPI，web 端从 OpenAPI 生成 TS 客户端，不手写请求代码

## 测试策略

| 类型 | 位置 | 作用 |
|---|---|---|
| 单元测试 | `tests/unit/` | 单个模块逻辑 |
| 契约测试 | `tests/conformance/` | 一套测试跑遍所有可替换实现（每个 ModelClient / Store / Tokenizer / Engine 都要过） |
| 恢复测试 | `tests/recovery/` | kill -9、配额耗尽、resume，验证设计原则第 2 条 |
| 回放 fixture | `tests/fixtures/` | 录制真实模型响应存盘，CI 回放 |

**CI 默认不打真实 API**：需要真实 API key 的测试单独打标记（`@pytest.mark.live`），本地手动跑，不进
默认 CI 流水线。

## 工具链

- **uv**：依赖与 workspace 管理
- **ruff**：lint + format（统一配置放 workspace 根 `pyproject.toml`）
- **ty**：类型检查
- **pytest**：测试
- **import-linter**：机械校验上面的依赖方向规则
- **pre-commit**：本地提交前跑 ruff + import-linter
- 统一入口走 `justfile`，不让各包各自记一串命令

## 版本与发布

- `packages/kernel` 走 semver，破坏性变更升 major，`CHANGELOG.md` 手写维护（不自动生成，要写清迁移方式）
- `apps/*` 不发版，跟部署走
- 内核的 `LICENSE` 需要单独定（开源必需，`apps/*` 不需要）——建议 Apache-2.0：给专利授权，基础设施类项目
  的通行选择

## 待定项

- 内核 LICENSE 具体选哪个
- web 前端技术栈（等真要开工时再定，不提前锁）
