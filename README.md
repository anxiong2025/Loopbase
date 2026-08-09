# Loopbase

**The open agent framework for finance — tools are capability, evidence is trust.**

Keep the loop moving. Keep the evidence honest.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14+-blue)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](packages/kernel/pyproject.toml)
[![Status](https://img.shields.io/badge/status-Stage%201-yellow)](ROADMAP.md)

[Roadmap](ROADMAP.md) · [Structure](STRUCTURE.md) · [简体中文](README.zh-CN.md)

Loopbase is an open agent harness for the finance domain: a provider-neutral, stdlib-only loop
kernel (`packages/kernel`) plus the finance tool layer (`packages/finance`). It keeps an agent's
thinking-acting loop reviewable and resumable — structured tools, provider-neutral model access,
and an append-only evidence log. The kernel stays domain-agnostic, so travel or other domains can
plug in later without changing it.

## Why Loopbase

An agent can finish a task in one session. Long-running work is harder: objectives drift, tools fail mid-run, evidence goes stale, and a model can spin forever on a bad tool result. Chat memory and a plain while-loop are not enough to govern that.

Loopbase keeps the durable loop state in one compact layer:

```
user goal
   │
   ▼
Loopbase: loop + tool registry + evidence log
   │
   ├─ model wants a tool? ──▶ execute → append evidence → continue
   │
   └─ model answered? ─────▶ stop, keep transcript + evidence
   │
   ▼
next turn (goals, quota, resume, handoff — later stages)
```

A useful mental model: Loopbase is the loop's operating record, not its brain. The model proposes; the kernel executes tools, records evidence, and decides when the loop may stop.

## What Loopbase is / is not

Loopbase is useful when you run:

- multi-step agent tasks that must be auditable after the fact;
- tool-using loops that must survive model or API differences;
- work that will later need goals, quota, recovery, and handoffs.

Loopbase is not:

- a multi-agent graph orchestration engine — interface only, Stage 8, not started;
- a UI or the iOS client — those are downstream consumers of this kernel;
- a hosted or multi-tenant service;
- a finance app or advisor — it's the harness underneath; domain logic lives in `packages/finance`, and the kernel stays domain-agnostic.

## Try it

Requirements: Python 3.14+ and [uv](https://docs.astral.sh/uv/) (or any Python 3.14 environment).

```bash
git clone https://github.com/anxiong2025/Loopbase.git
cd Loopbase
uv sync
```

Run the real-model demo (prints every request/response body; needs an API key):

```bash
cp .env.example .env   # fill in your API key / base_url / model
uv run examples/stage2_finance/demo.py
```

Run the unit tests:

```bash
uv run --project packages/kernel --extra dev pytest packages/kernel/tests/unit -q
```

## Capabilities (current)

| Capability | What it does |
|---|---|
| ReAct loop | Runs model ↔ tool turns until the model answers or max turns is reached |
| Tool registry | JSON-Schema tool definitions with runtime registration; errors feed back to the model |
| Model clients | Provider-neutral `ModelClient` protocol; OpenAI/DeepSeek and Anthropic dialects |
| Evidence log | Append-only JSONL with schema version, timestamp, and id per state transition |
| Config | Minimal `.env` loading; no credentials in code |

## Roadmap

| Stage | What | Status |
|---|---|---|
| 0–1 | Minimal ReAct loop, tool registry, model dialects, evidence log | ✅ done (v0.1.0) |
| 2 | Structured goals and task management | next |
| 3 | Parallel and dependent multi-tool orchestration | planned |
| 4 | Persistent state, checkpoint recovery, provenance | planned |
| 5 | Context budget, compression, memory layers | planned |
| 6 | Quota-aware lifecycle and resume | planned |
| 7 | Verifiable handoffs | planned |
| 8 | Graph orchestration (outside the kernel) | not started |

Full detail: [ROADMAP.md](ROADMAP.md).

## Design principles

Each principle must be falsifiable by a concrete test:

1. The core loop has zero mandatory runtime dependencies — `kernel/` runs the minimal loop with stdlib only.
2. Safe to checkpoint and fully recover at any moment.
3. Every state transition has auditable evidence.
4. Core loop, model backends, tools, and domain logic are decoupled.
5. Real-world actions must pass the policy layer.

## Repository layout

```
packages/kernel/   the open-source deliverable: domain-agnostic, stdlib-only
packages/finance/  finance domain (current): tool impls, prompts, goal templates
packages/travel/   travel domain (planned): tool impls, prompts, goal templates
apps/              api / web / ios clients (consumers, later)
examples/          runnable stage demos
schemas/           language-neutral JSON Schemas (source of truth)
```

See [STRUCTURE.md](STRUCTURE.md) for the full contract.

## Current status

v0.1.0 — early but usable single-agent loop kernel. Stages 0–1 are complete: minimal ReAct loop, runtime tool registration, OpenAI/DeepSeek + Anthropic dialects, evidence log, 8 passing unit tests, and a key-free demo. It is not a full agent platform, not a graph engine, and not an autonomous production controller.

## Contributing

Loopbase is early. The most useful feedback comes from real long-running agent projects: where the loop helped, where it felt heavy, and which controls disappeared from view. Open an issue for bugs and feature requests; PRs for small, public-safe improvements.

## License

Apache-2.0. See [LICENSE](LICENSE).
