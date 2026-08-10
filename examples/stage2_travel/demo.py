"""旅行攻略 demo：通用内核 + 旅行工具集。

直接对接内核 ReActLoop / OpenAICompatibleClient，只注册旅行工具集
（travel_agent.tools），演示内核的领域无关性。每轮打印发出去的请求
body 与模型原始响应，便于观察 function calling 的完整流程与停止条件。
同时把完整对话（每轮请求/响应、工具定义、最终答案）写入 transcript.json，
并把同一份内容渲染成易读的 transcript.md（按轮分节），方便离线复盘学习。

跑法（先 uv sync 安装 travel-agent）：
    uv sync
    uv run examples/stage2_travel/demo.py
    uv run examples/stage2_travel/demo.py "帮我做一份北京三日游攻略"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from loopbase import (
    Goal,
    JsonlEvidenceLog,
    OpenAICompatibleClient,
    ReActLoop,
    ToolRegistry,
)
from loopbase.config import load_dotenv
from loopbase.models.openai_dialect import _encode_message

from travel_agent import build_system_prompt
from travel_agent.tools import register_all

DEMO_DIR = Path(__file__).resolve().parent


class VerboseClient:
    """包装真实客户端，打印每次请求的 body 与原始响应。"""

    def __init__(self, client: OpenAICompatibleClient) -> None:
        self.client = client
        self.records: list[dict] = []

    def complete(self, messages, tools):
        body = {
            "model": self.client.model,
            "messages": [_encode_message(m) for m in messages],
            "tools": [
                {"type": "function", "function": spec.as_dict()} for spec in tools
            ],
        }
        print("\n>>> 请求 body：")
        print(json.dumps(body, ensure_ascii=False, indent=2))

        response = self.client.complete(messages, tools)

        print("\n>>> 模型原始响应：")
        print(json.dumps(response.raw, ensure_ascii=False, indent=2))
        self.records.append({"request": body, "response": response.raw})
        return response


def _clip(text: str, limit: int = 300) -> str:
    """超长文本截断，保持 Markdown 可扫读。"""
    return text if len(text) <= limit else text[:limit] + " …"


def _render_messages(messages: list[dict]) -> list[str]:
    """把请求里的 messages 渲染成 Markdown 列表。"""
    lines: list[str] = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            content = _clip(message["content"])
            lines.append(
                f"- **tool**（id: `{message['tool_call_id']}`）：{content}"
            )
        elif role == "assistant" and message.get("tool_calls"):
            calls = "、".join(
                f"`{call['function']['name']}({call['function']['arguments']})`"
                for call in message["tool_calls"]
            )
            content = message.get("content") or ""
            line = f"- **assistant**（调用工具：{calls}）"
            lines.append(line if not content else f"{line}：{content}")
        else:
            lines.append(f"- **{role}**：{message.get('content', '')}")
    return lines


def build_transcript_md(transcript: dict) -> str:
    """把完整对话渲染成按轮分节的 Markdown 文档。"""
    lines = [
        "# 对话记录",
        "",
        f"- 模型：`{transcript['model']}`",
        f"- 接口：`{transcript['base_url']}`",
        f"- 系统提示词：{transcript['system_prompt']}",
        f"- 用户问题：{transcript['user_input']}",
        f"- 轮数：{transcript['turns']} · 停止原因：`{transcript['stopped_by']}`",
        f"- 执行工具：{', '.join(transcript['tool_calls_executed']) or '无'}",
        "",
        "## 工具定义",
        "",
    ]
    lines.extend(
        f"- `{spec['name']}`：{spec['description']}" for spec in transcript["tools"]
    )

    for round_ in transcript["rounds"]:
        lines.extend(
            [
                "",
                f"## 第 {round_['turn']} 轮",
                "",
                "### 请求",
                "",
                *_render_messages(round_["request"]["messages"]),
                "",
                "### 响应",
                "",
            ]
        )
        choice = round_["response"]["choices"][0]
        lines.append(f"- finish_reason：`{choice.get('finish_reason')}`")
        usage = round_["response"].get("usage") or {}
        if usage:
            lines.append(
                f"- usage：prompt {usage.get('prompt_tokens')} · "
                f"completion {usage.get('completion_tokens')}"
            )
        message = choice.get("message") or {}
        for index, call in enumerate(message.get("tool_calls") or [], start=1):
            fn = call["function"]
            lines.append(
                f"- 工具调用 {index}：`{fn['name']}({fn['arguments']})`"
                f"（id: `{call['id']}`）"
            )
        content = message.get("content")
        if content:
            lines.extend(["", "内容：", "", "> " + content.replace("\n", "\n> ")])

    lines.extend(
        [
            "",
            "## 最终回答",
            "",
            "> " + (transcript["final_answer"] or "(无)").replace("\n", "\n> "),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    load_dotenv()  # 加载 .env；已有环境变量优先
    api_key = (
        os.environ.get("LOOPBASE_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("MOONSHOT_API_KEY")
    )
    if not api_key:
        sys.exit("未找到 API key，请配置 .env（参考 .env.example）。")
    base_url = os.environ.get("LOOPBASE_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LOOPBASE_MODEL", "deepseek-chat")

    tools = ToolRegistry()
    register_all(tools)

    system_prompt = build_system_prompt()

    real = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
    verbose = VerboseClient(real)
    loop = ReActLoop(
        client=verbose,
        tools=tools,
        max_turns=5,
        system_prompt=system_prompt,
        evidence_log=JsonlEvidenceLog(DEMO_DIR / "evidence_travel.jsonl"),
    )

    print(f">>> 开始循环：{model} @ {base_url}\n")
    user_input = (
        " ".join(sys.argv[1:])
        or "为我设计一份北京三日游攻略，查询天气和景点资料，并给出3000元预算分配建议。"
    )
    goal = Goal(
        objective=user_input,
        success_criteria=["给出三天每日安排", "列出预算构成", "标明需要复核的实时信息"],
        constraints=["总预算不超过3000元", "不得编造实时交通和酒店价格"],
        context={"destination_city": "北京", "days": 3, "budget": 3000},
    )
    result = loop.run(goal)

    transcript = {
        "model": model,
        "base_url": base_url,
        "system_prompt": system_prompt,
        "user_input": user_input,
        "goal": goal.as_dict(),
        "tools": [spec.as_dict() for spec in tools.specs()],
        "turns": result.turns,
        "stopped_by": result.stopped_by,
        "tool_calls_executed": result.tool_calls_executed,
        "final_answer": result.final_answer,
        "rounds": [
            {"turn": index, **record}
            for index, record in enumerate(verbose.records, start=1)
        ],
    }
    transcript_path = DEMO_DIR / "transcript.json"
    transcript_path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    transcript_md_path = DEMO_DIR / "transcript.md"
    transcript_md_path.write_text(
        build_transcript_md(transcript),
        encoding="utf-8",
    )

    print(f"\n最终回答：{result.final_answer}")
    print(f"轮数：{result.turns}，停止原因：{result.stopped_by}")
    print(f"执行的工具：{result.tool_calls_executed}")
    print(f"\n证据日志已写入：{(DEMO_DIR / 'evidence_travel.jsonl').resolve()}")
    print(f"完整对话记录已写入：{transcript_path.resolve()}")
    print(f"可读版对话记录已写入：{transcript_md_path.resolve()}")


if __name__ == "__main__":
    main()
