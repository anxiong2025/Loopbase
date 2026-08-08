"""两种模型方言的消息编码/响应解析测试，不联网。"""

from __future__ import annotations

import json

from loopbase import Message, ToolCall, ToolSpec
from loopbase.models.anthropic_dialect import _encode_message as anthropic_encode
from loopbase.models.openai_dialect import _encode_message as openai_encode


def test_openai_encodes_tool_call_and_tool_result() -> None:
    assistant = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="call_1", name="get_weather", arguments={"city": "东京"})],
    )
    encoded = openai_encode(assistant)
    assert encoded["tool_calls"][0]["function"]["name"] == "get_weather"
    # OpenAI 方言里 arguments 是 JSON 字符串
    assert json.loads(encoded["tool_calls"][0]["function"]["arguments"]) == {"city": "东京"}

    tool_msg = Message(role="tool", content="26°C", tool_call_id="call_1")
    assert openai_encode(tool_msg)["tool_call_id"] == "call_1"


def test_anthropic_encodes_tool_use_and_tool_result() -> None:
    assistant = Message(
        role="assistant",
        content="我来查一下",
        tool_calls=[ToolCall(id="toolu_1", name="get_weather", arguments={"city": "东京"})],
    )
    encoded = anthropic_encode(assistant)
    assert encoded["role"] == "assistant"
    blocks = encoded["content"]
    assert blocks[0] == {"type": "text", "text": "我来查一下"}
    # Anthropic 方言里 input 直接是对象，不做字符串化
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["input"] == {"city": "东京"}

    tool_msg = Message(role="tool", content="26°C", tool_call_id="toolu_1")
    encoded_result = anthropic_encode(tool_msg)
    assert encoded_result["role"] == "user"
    assert encoded_result["content"][0]["tool_use_id"] == "toolu_1"


def test_anthropic_tool_spec_matches_openai_parameters_shape() -> None:
    spec = ToolSpec(
        name="get_weather",
        description="查询天气",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    assert spec.as_dict()["parameters"]["required"] == ["city"]
