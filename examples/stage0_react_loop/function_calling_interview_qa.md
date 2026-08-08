# Function Calling 面试问答整理

配套代码：`function_calling_loop.py`（跑一遍能看到真实的 request/response）

---

## 7. Function Calling 是怎样的过程？

一句话：**宿主给模型一份工具清单，模型只输出"调用意图"（不会真的执行），宿主本地执行拿到真实结果，把结果回填进对话历史，再问模型一次——如此循环，直到模型不再要求调用工具。**

时间线（以问"东京天气"为例）：

```
第 1 轮请求（messages: 1条 + tools清单）
        │
        ▼
模型返回 tool_calls（意图，不是结果）＋ finish_reason="tool_calls"
        │
        ▼
宿主：存模型意图 → 本地执行真实函数 → 拿到结果 → 回填成新消息
        │
        ▼
第 2 轮请求（messages: 4条，全量重发）
        │
        ▼
模型返回最终文字回答 ＋ finish_reason="stop"  →  循环结束
```

关键认知：**API 是无状态的**。第 2 轮请求会把第 1 轮的全部历史原样重发一遍，只是尾部多了两条消息（模型的 tool_calls + 回填的结果）。这也是为什么多轮对话上下文会越滚越大、每轮都要重复付费。

---

## 8. Function Calling 包含哪些步骤？

1. **工具定义**：宿主把工具写成 JSON Schema（`name` + `description` + 参数结构），`description` 是给模型看的自然语言，模型全靠这段话判断用不用、怎么用。
2. **每轮请求都携带工具清单**：不是只发一次，是**每一轮**请求都要把 `tools` 字段重新塞进 body——模型自己不"记得"有哪些工具存在。
3. **模型生成意图**：模型判断要不要调用工具、调哪个、传什么参数，输出结构化的 `tool_calls`（不是执行，只是"意图"）。
4. **宿主解析 + 本地执行**：解析出函数名和参数，调用本地真实写好的函数，拿到真实结果（模型没有网络、没有执行环境，做不到这一步）。
5. **结果回填**：把执行结果包装成新消息（带上能跟原调用对应的 ID），加进历史。
6. **带着全部历史再发一次请求**：模型看到结果后生成最终回答，或者决定继续调用下一个工具。
7. **循环终止判断**：看 `finish_reason`（或 Anthropic 的 `stop_reason`）是否为 `"stop"` / `"end_turn"`，是则结束；否则回到步骤 3。

对应代码位置：
- 工具定义 → `function_calling_loop.py:35-50`（`TOOLS`）
- 每轮携带 → `function_calling_loop.py:74-79`（`call_model` 里 `"tools": TOOLS`）
- 循环主体 → `function_calling_loop.py:104-152`

---

## 9. 模型怎么知道有哪些 Function 可以调用？

**它不知道，是宿主每次请求时告诉它的。**

模型本身没有任何"记忆"说自己能用什么工具。宿主（你的代码/Claude Code/某个 App）在组装请求体时，把这次要开放给模型的工具列表塞进 `tools` 字段一起发过去。模型看到这次请求里列出了哪些工具描述，就只能在这些里面选——**工具清单是运行时决定的输入，不是模型内置的能力**。

典型误区（面试原话反复问的点）：
> "一个大模型可能接到 Claude Code 上，也可能接到手机 App 上，那它们之间的 function 或 tool 都是不一样的呀，那它怎么知道自己能用哪些工具？"

答案：**因为每次接入不同的宿主，宿主组装的 `tools` 清单不同**——同一个模型，Claude Code 塞给它 Bash/Read/Edit 之类的工具，手机 App 可能塞给它拍照/发短信之类的工具。模型不是"知道自己能用哪些"，而是"这次请求给它看什么，它就只能选什么"。

MCP（Model Context Protocol）本质上就是让宿主能**动态扩展**塞进 `tools` 字段的清单（比如连上 Figma MCP server 后，多了 20 多个 Figma 相关工具），跟模型本身的能力无关。

---

## 10. Function 是模型自己决定的吗？

这里要拆成两个完全不同的问题，很多人会混在一起答错：

| 问题 | 谁决定 |
|---|---|
| **有哪些 function 可用**（清单） | **宿主**决定，每轮请求塞进 `tools` 字段 |
| **要不要调用、调哪个、传什么参数、什么时候停** | **模型自己**判断 |

模型自己决定的部分，具体体现：
- 看到 `tools` 清单 + 用户意图后，自己判断"这一轮需不需要调用工具"
- 如果需要，自己选择调用哪个/哪几个（可能并行调用多个）
- 自己生成参数值
- 自己判断"当前信息是否已经足够回答用户"，决定是继续调用还是直接给最终答案（体现为 `finish_reason` 是 `"tool_calls"` 还是 `"stop"`）

**但宿主可以覆盖模型的判断权**（面试加分点）：
- `tool_choice: "required"` — 强制这一轮必须调用某个工具，不许直接回答
- `tool_choice: {"type": "function", "function": {"name": "get_weather"}}` — 强制调用**指定**的工具
- `tool_choice: "none"` — 禁止调用任何工具，即使清单里有
- 默认是 `"auto"`，即完全交给模型自主判断

**权限边界也是宿主控制的，不是模型自己知道的**——比如子 agent 能不能创建下一层子 agent，是主 agent 的代码逻辑决定要不要把"创建子 agent"这个工具塞进子 agent 能看到的 tools 列表里，不是子 agent 自己"知道"有没有权限。

---

## 11. Tool 是怎么传给模型的？

通过每次请求 body 里的 `tools`（OpenAI/DeepSeek）或同名字段（Anthropic）传过去，是一个**数组**，每个元素描述一个工具。

### OpenAI / DeepSeek 格式（嵌套）

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "查询指定城市的实时天气。用户问天气、气温、冷热、是否下雨时使用。",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {"type": "string", "description": "城市名，如：东京、北京"}
      },
      "required": ["city"]
    }
  }
}
```

### Anthropic（Claude）格式（扁平）

```json
{
  "name": "get_weather",
  "description": "查询指定城市的实时天气",
  "input_schema": {
    "type": "object",
    "properties": {
      "city": {"type": "string", "description": "城市名，例如：东京"},
      "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
    },
    "required": ["city"]
  }
}
```

多个工具就是数组里多加几个 dict，宿主执行时按 `name` 去查映射表（`TOOL_IMPLS`）找到对应的本地函数，跟工具数量无关，逻辑是通用的。

`description` 字段是重点——模型完全靠这段自然语言判断"什么时候该用这个工具"，写得越清楚，模型调用越准确。这也是 prompt engineering 在 function calling 里的应用点。

---

## 12. Tool 执行完之后流程是什么？

执行完 = 拿到真实结果之后，要做「回填」，再进入下一轮：

1. **本地执行**：宿主解析 `tool_calls` 里的 `name` + `arguments`，调用本地真实函数，得到结果（成功结果或报错信息）。
2. **错误也要回填，不能崩溃**：
   ```python
   try:
       result = TOOL_IMPLS[name](**args)
   except Exception as exc:
       result = f"执行失败: {exc}"   # 报错也当结果回填，让模型自己纠正
   ```
   这是 agent 系统"自我纠错"能力的来源——模型下一轮完全基于回填的内容判断要不要换参数重试。
3. **回填**：把结果包装成一条新消息，加进 `messages`，用 ID 跟原调用请求对应上：
   - OpenAI/DeepSeek：`{"role": "tool", "tool_call_id": tc["id"], "content": result}`
   - Anthropic：塞进一条 `role: "user"` 消息里的 `tool_result` block，配对字段叫 `tool_use_id`
4. **带着全部历史（含刚回填的这条）再发一次请求**——这一步会把之前所有轮次的消息原样重发，不是只发新增的部分。
5. **模型看到结果，继续判断**：信息够了就直接生成文字回答（`finish_reason: "stop"`）；不够就再生成一轮 `tool_calls`，回到步骤 1。
6. **宿主要有兜底熔断**：不能无限信任模型的判断，防止模型反复觉得"信息不够"导致死循环。脚本里是 `for turn in range(1, 6)`，最多跑 5 轮强制停。

**多轮场景下回填次数 = 有工具调用的轮次数**：如果跑了 5 轮，前 4 轮都返回了 `tool_calls`，那就回填 4 次；第 5 轮如果是 `"stop"`，那一轮不用回填，循环直接结束。

安全考点：工具执行结果是**外部数据**（网络请求/数据库/文件的返回内容），回填进去时要当成不可信输入处理，防止里面混入恶意构造的文字导致提示注入（prompt injection）。

---

## 13. 大模型 API 的输入输出是什么？

### 输入（request body）

```json
{
  "model": "deepseek-chat",
  "messages": [ /* 完整对话历史，每次全量发送 */ ],
  "tools": [ /* 工具清单，每轮都要带 */ ]
}
```

- `messages`：数组，每条有 `role`（`user`/`assistant`/`tool`/`system`）和 `content`，代表迄今为止的全部对话历史——**API 无状态，所谓"记忆"就是宿主自己维护这个数组并每次全量重发**。
- `tools`：本轮开放给模型的工具清单（见问题 11）。
- 可选控制参数：`tool_choice`（见问题 10）、`stream`（是否流式输出）等。

### 输出（response body，不调用工具的情况）

```json
{
  "id": "...",
  "object": "chat.completion",
  "created": 1785851334,
  "model": "deepseek-v4-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "最终的文字回答"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 385,
    "completion_tokens": 96,
    "total_tokens": 481
  }
}
```

### 输出（response body，模型要调用工具的情况）

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "我来帮你查一下东京的天气情况。",
        "tool_calls": [
          {
            "id": "call_00_o95gquGR14uZx3RjIlTa4304",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"city\": \"东京\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": { "prompt_tokens": 311, "completion_tokens": 53, "total_tokens": 364 }
}
```

字段拆解：
- `content`：模型说的普通文字（可能和 `tool_calls` **同时存在**，比如先说"我来帮你查一下"再附带调用意图）。
- `tool_calls`：数组，因为模型一轮可能**并行**调用多个工具。每项包含：
  - `id`：本次调用的唯一编号，回填结果时用它对应（`tool_call_id`）
  - `function.name`：要调用的函数名
  - `function.arguments`：**JSON 字符串**（不是对象！要 `json.loads()` 二次解析——这是 OpenAI 系的坑，Anthropic 的 `input` 直接是对象）
- `finish_reason`：方向盘字段。`"tool_calls"` = 还要继续循环；`"stop"` = 模型给出最终答案，循环结束。
- `usage`：token 用量，`prompt_tokens` 会随着轮数增加而上涨（因为每轮全量重发历史），是成本曲线的直接体现。

### Anthropic（Claude）的等价结构对照

```json
{
  "content": [
    {"type": "text", "text": "我来帮你查一下..."},
    {"type": "tool_use", "id": "toolu_xxx", "name": "get_weather", "input": {"city": "东京"}}
  ],
  "stop_reason": "tool_use"
}
```

---

## 两种方言对照表（面试加分项）

|                | OpenAI / DeepSeek         | Anthropic                        |
|----------------|----------------------------|-----------------------------------|
| 停止信号        | `finish_reason="tool_calls"` | `stop_reason="tool_use"`        |
| 调用参数        | `arguments`（JSON 字符串）   | `input`（直接是对象）             |
| 结果回填 role   | `"tool"`                   | `"user"`（塞 `tool_result` block） |
| 配对字段        | `tool_call_id`             | `tool_use_id`                    |
| 工具定义嵌套    | `{type, function:{...}}`   | 扁平 `{name, description, input_schema}` |

本质完全一样：**模型只输出意图，宿主执行，结果回填，循环。**

---

## 补充考点（可能追问）

- **`tool_choice`**：默认 `"auto"` 交给模型判断，但宿主可以用 `"required"` / 指定某个工具 / `"none"` 夺回控制权。
- **并行调用**：一轮 `tool_calls` 数组可能有多项（比如"上海和北京哪个凉快"会同时查两个城市）；如果工具间有依赖关系（B 依赖 A 的结果），可以用 `parallel_tool_calls: false` 强制顺序调用。
- **Streaming**：开启流式后 `tool_calls` 是分片到达的（先给 `name`，`arguments` 逐字符流出），宿主要自己拼接完再解析。
- **Function calling ≠ JSON mode**：JSON mode 只是让模型输出符合 JSON 格式的普通回答，没有工具、没有循环、没有回填，是完全不同的两件事。
- **ReAct 与 function calling 的关系**：ReAct（Reason + Act）描述的是 agent 的思考-行动循环这个更高层的模式；function calling 是"行动"这一步在 API 层面具体怎么实现的机制。
