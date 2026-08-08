#!/usr/bin/env python3
"""
Function Calling 完整闭环 —— DeepSeek 版，零依赖（只用标准库）。

跟上一版的区别：这次【跑完整两轮】。
单跑一轮只能看到"模型想调工具"，看不到最关键的两件事：
  - 结果怎么回填（role 是 "tool"，要带 tool_call_id）
  - 第二轮必须把【全部历史】原样重发（API 是无状态的）

运行：
    export DEEPSEEK_API_KEY=sk-xxx        # 别写进代码
    python3 function_calling_loop.py
    python3 function_calling_loop.py "上海和北京哪个凉快"   # 试试并行调用
"""

import json
import os
import sys
import urllib.error
import urllib.request


def load_dotenv(path: str = ".env") -> None:
    """极简 .env 加载器，不引入 python-dotenv 依赖。已存在的环境变量优先级更高。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or sys.exit(
    "请先设置环境变量：export DEEPSEEK_API_KEY=sk-xxx（或在 .env 文件里配置，参考 .env.example）"
)
URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"  # 注意：deepseek-reasoner 不支持 function calling
PROMPT = " ".join(sys.argv[1:]) or "我明晚飞东京，那边天气怎么样？"


# ============================================================================
# 1. 工具定义 —— 就是一坨普通的 dict
#    模型不"知道"这个工具存在。是我们【每一轮请求】都把它塞进 body 里的。
#    description 是写给模型看的自然语言，它靠这段话决定用不用、怎么用。
# ============================================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气。用户问天气、气温、冷热、是否下雨时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如：东京、北京"},
                },
                "required": ["city"],
            },
        },
    }
]


# ============================================================================
# 2. 工具的真实实现。模型永远不会执行这个函数 —— 只有我们的代码会。
# ============================================================================
def get_weather(city: str) -> str:
    fake_db = {
        "东京": "26°C 晴，湿度 60%",
        "北京": "32°C 晴，东南风 2 级",
        "上海": "28°C 小雨",
    }
    return fake_db.get(city, f"暂无 {city} 的天气数据")


TOOL_IMPLS = {"get_weather": get_weather}


def dump(label: str, obj) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def call_model(messages: list) -> dict:
    body = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,  # ← 每一轮都要重新传，模型自己不记得有哪些工具
    }
    dump("① 发出去的 REQUEST BODY", body)

    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:500]}")

    dump("② 收到的 RESPONSE BODY", data)
    return data


def main() -> None:
    # 这个 list 就是全部的"记忆"。API 本身完全无状态。
    messages = [{"role": "user", "content": PROMPT}]

    for turn in range(1, 6):  # 熔断：最多 5 轮
        print(f"\n\n{'#' * 72}\n#  第 {turn} 轮\n{'#' * 72}")

        data = call_model(messages)
        choice = data["choices"][0]
        msg = choice["message"]

        # --------------------------------------------------------------
        # 【看这里 1】finish_reason 是整个 agent loop 的方向盘
        #   "tool_calls" → 模型想调工具，循环继续
        #   "stop"       → 模型给出最终答案，循环结束
        # （Anthropic 那边这个字段叫 stop_reason，值叫 tool_use / end_turn）
        # --------------------------------------------------------------
        print(f"\n>>> finish_reason = {choice['finish_reason']!r}")
        print(f">>> usage = {data['usage']}")

        # 模型的回复原样存进历史（包括它的 tool_calls）
        messages.append(msg)

        if not msg.get("tool_calls"):
            print(f"\n>>> 最终回答：{msg['content']}")
            print(f"\n>>> 跑了 {turn} 轮，messages 里现在有 {len(messages)} 条消息")
            break

        # --------------------------------------------------------------
        # 【看这里 2】模型返回的不是天气，是一段"调用意图"
        #   它没有网络、没有执行环境，只是生成了一段 JSON。
        #   下面这个 for 循环 —— 我们的代码 —— 才是真正干活的地方。
        # --------------------------------------------------------------
        for tc in msg["tool_calls"]:
            name = tc["function"]["name"]
            # 坑：OpenAI 方言里 arguments 是【字符串】，要二次解析
            # （Anthropic 那边 input 直接就是对象，不用这一步）
            args = json.loads(tc["function"]["arguments"])
            print(f"\n>>> 模型想调用: {name}({args})   id={tc['id']}")

            try:
                result = TOOL_IMPLS[name](**args)
            except Exception as exc:
                result = f"执行失败: {exc}"  # 报错也回填，让模型自己纠正，别 crash
            print(f">>> 我们本地执行的真实结果: {result}")

            # ----------------------------------------------------------
            # 【看这里 3】结果回填：role 是 "tool"，必须带 tool_call_id 对上号
            #   （Anthropic 那边是塞进一条 role:"user" 的 tool_result block）
            # ----------------------------------------------------------
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result}
            )

    print(
        """
────────────────────────────────────────────────────────────────────────
现在做一件事，比读代码有用十倍：

  翻回上面，把【第 1 轮的 REQUEST BODY】和【第 2 轮的 REQUEST BODY】并排对比。

第二轮把第一轮的全部内容原样又发了一遍，只是尾部多了两条。
这一眼看懂，三个概念同时通了：
  · API 是无状态的 —— 所谓"多轮记忆"就是你每次全量重发
  · 上下文为什么会爆 —— 每轮都在累加，且要重复付费
  · 为什么要压缩、为什么压缩会让 KV cache 失效 —— 前缀被改写了

再看 usage 里 prompt_tokens 两轮的变化，这就是成本曲线。
────────────────────────────────────────────────────────────────────────

两种方言对照（面试可能会问，知道差异是加分项）：

                    OpenAI / DeepSeek          Anthropic
  停止信号          finish_reason="tool_calls"  stop_reason="tool_use"
  调用参数          arguments（JSON 字符串）    input（直接是对象）
  结果回填 role     "tool"                      "user"
  配对字段          tool_call_id                tool_use_id
  工具定义嵌套      {type,function:{...}}       扁平 {name,description,input_schema}

本质完全一样：模型只输出意图，宿主执行，结果回填，循环。
"""
    )


if __name__ == "__main__":
    main()
