"""Stage 1 内核演示：不依赖 API key，用脚本化模型驱动循环。

演示内容：
  1. 运行时注册工具（get_weather）
  2. ReAct 循环：模型想调工具 → 我们执行 → 结果回填 → 模型给最终答案
  3. 证据日志：循环每一步都写进 evidence.jsonl

跑法（examples 不在 uv workspace 里，借内核包的 venv 执行）：
    cd packages/kernel && uv run --extra dev python ../../examples/stage1_kernel/demo.py
"""

from __future__ import annotations

from pathlib import Path

from loopbase import (
    JsonlEvidenceLog,
    Message,
    ModelResponse,
    ReActLoop,
    ToolCall,
    ToolRegistry,
)


class ScriptedModel:
    """按脚本返回响应的假模型，用于演示（真实使用换成 OpenAICompatibleClient）。"""

    def __init__(self) -> None:
        self.step = 0

    def complete(self, messages, tools):
        self.step += 1
        if self.step == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(id="call_1", name="get_weather", arguments={"city": "东京"})
                    ],
                ),
                finish_reason="tool_calls",
                usage={"prompt_tokens": 18, "completion_tokens": 9},
            )
        return ModelResponse(
            message=Message(
                role="assistant",
                content="东京现在 26°C，晴天，湿度 60%，适合出门。",
            ),
            finish_reason="stop",
            usage={"prompt_tokens": 40, "completion_tokens": 12},
        )


def main() -> None:
    tools = ToolRegistry()
    tools.register(
        name="get_weather",
        description="查询指定城市的实时天气",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名，如：东京"}},
            "required": ["city"],
        },
        impl=lambda city: {"东京": "26°C 晴，湿度 60%"}.get(city, f"暂无 {city} 数据"),
    )

    log_path = Path("evidence.jsonl")
    loop = ReActLoop(
        client=ScriptedModel(),
        tools=tools,
        max_turns=5,
        system_prompt="你是旅行助手。查完天气后用中文简洁回答。",
        evidence_log=JsonlEvidenceLog(log_path),
    )

    print(">>> 开始运行循环（脚本化模型）...\n")
    result = loop.run("东京现在天气怎么样？")

    print(f"最终回答：{result.final_answer}")
    print(f"轮数：{result.turns}，停止原因：{result.stopped_by}")
    print(f"执行的工具：{result.tool_calls_executed}")
    print(f"\n证据日志已写入：{log_path.resolve()}")
    print("日志内容（每条状态转移一行）：")
    for record in JsonlEvidenceLog(log_path).read_all():
        print(f"  [{record.kind}] {record.payload}")


if __name__ == "__main__":
    main()
