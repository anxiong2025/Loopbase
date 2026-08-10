# Loopbase

**A lazy-friendly travel-planning agent — state the goal and let the loop do the legwork.**

Keep the loop moving. Keep the evidence honest.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14+-blue)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](packages/kernel/pyproject.toml)
[![Status](https://img.shields.io/badge/status-Stage%202%20in%20progress-orange)](ROADMAP.md)

[Roadmap](ROADMAP.md) · [Structure](STRUCTURE.md) · [简体中文](README.zh-CN.md)

Loopbase is an open agent harness with travel planning as its first product domain. A provider-neutral,
stdlib-only runtime kernel (`packages/kernel`) runs beneath a travel tool package (`packages/travel`).
Users describe the destination, duration, and budget; the agent plans tasks, gathers information,
uses tools, and produces an itinerary that is ready to follow. The kernel remains domain-agnostic and
contains no travel-specific logic.

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
- a booking or payment platform — the current scope plans trips and gathers information, but does not purchase tickets or rooms.

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
uv run examples/stage2_travel/demo.py
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
| Structured goals | Versioned `goal/v1` data with objective, success criteria, constraints, and context |
| Natural-language intake | `/run` turns one user prompt into a Goal or returns only blocking clarification questions |
| Task planning | Model-proposed tasks; runtime-owned ids, dependency DAG validation, and lifecycle states |
| Task execution | Dependency-aware serial execution with result passing and failed-branch isolation |
| Travel tools | Weather, travel-place research, location distance, and deterministic budget totals |
| Config | Minimal `.env` loading; no credentials in code |

## Roadmap

| Stage | What | Status |
|---|---|---|
| 0–1 | Minimal ReAct loop, tool registry, model dialects, evidence log | ✅ done (v0.1.0) |
| 2 | Structured goals and task management | 🚧 intake, planning, and serial execution done; replanning next |
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
packages/travel/   travel-planning domain: tools, provider adapters, and prompts
apps/              api / web / ios clients (consumers, later)
examples/          runnable stage demos
schemas/           language-neutral JSON Schemas (source of truth)
```

See [STRUCTURE.md](STRUCTURE.md) for the full contract.

## Current status

v0.1.0 plus Stage 2 development — early but usable single-agent loop kernel. Stages 0–1 are complete; Stage 2 now has natural-language goal intake, model-proposed/runtime-validated task plans, and serial dependency-aware task execution through the ReAct loop. Replanning is next. It is not a full agent platform, not a graph engine, and not an autonomous production controller.

## Contributing

Loopbase is early. The most useful feedback comes from real long-running agent projects: where the loop helped, where it felt heavy, and which controls disappeared from view. Open an issue for bugs and feature requests; PRs for small, public-safe improvements.

## License

Apache-2.0. See [LICENSE](LICENSE).
