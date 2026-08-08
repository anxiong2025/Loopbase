#!/usr/bin/env python3
import json
import os
import sys
import time
import tomllib
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path.home() / ".kimi" / "config.toml"
CRED_PATH = Path.home() / ".kimi" / "credentials" / "kimi-code.json"
OAUTH_TOKEN_URL = "https://auth.kimi.com/api/oauth/token"
CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"  # Kimi CLI 公开 client_id（见 kimi_cli/auth/oauth.py）
MODEL = os.environ.get("DEMO_MODEL", "kimi-k3")      # 你本机 CLI 的默认模型
PROMPT = " ".join(sys.argv[1:]) or "我明晚飞东京，那边现在天气怎么样？用摄氏度回答。"

TOOL = {
    "name": "get_weather",
    "description": "查询指定城市的实时天气",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，例如：东京"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city"],
    },
}


def post(url: str, *, headers: dict, json_body=None, form=None) -> tuple[int, dict]:
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers = {**headers, "content-type": "application/json"}
    else:
        data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def get_access_token() -> str:
    # 最优先：显式指定的 Moonshot 开放平台 API key
    if key := os.environ.get("MOONSHOT_API_KEY"):
        return key
    # 其次：config.toml 里托管 provider 的静态 api_key（CLI 登录后写入的）
    if CONFIG_PATH.exists():
        cfg = tomllib.loads(CONFIG_PATH.read_text())
        for prov in (cfg.get("providers") or {}).values():
            key = (prov or {}).get("api_key")
            if key:
                return key
    # 否则走 OAuth refresh_token 换新
    cred = json.loads(CRED_PATH.read_text())
    if time.time() < float(cred.get("expires_at", 0)) - 60:
        return cred["access_token"]

    print("[auth] access_token 已过期，用 refresh_token 换新 ...")
    device_id_path = CRED_PATH.parent.parent / "device_id"
    headers = {"X-Msh-Platform": "kimi_cli"}
    if device_id_path.exists():
        headers["X-Msh-Device-Id"] = device_id_path.read_text().strip()
    status, data = post(
        OAUTH_TOKEN_URL,
        headers=headers,
        form={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": cred["refresh_token"],
        },
    )
    if status != 200:
        sys.exit(f"[auth] 刷新失败 HTTP {status}: {data}\n"
                 f"       请先随便跑一次 kimi CLI 让它重新登录，或改用 Moonshot 开放平台的 API key。")

    # 与 CLI 相同的格式写回，避免 CLI 下次用到被轮换掉的旧 refresh_token
    new_cred = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + float(data["expires_in"]),
        "scope": data.get("scope", cred.get("scope", "")),
        "token_type": data.get("token_type", "Bearer"),
        "expires_in": float(data["expires_in"]),
    }
    CRED_PATH.write_text(json.dumps(new_cred, indent=2))
    os.chmod(CRED_PATH, 0o600)
    print("[auth] 新 token 已写回", CRED_PATH)
    return new_cred["access_token"]


def show_anthropic(data: dict) -> None:
    print("=" * 64)
    print("stop_reason =", data.get("stop_reason"), "  <- 出现 tool_use：模型想调工具，主动停下")
    print("=" * 64)
    for block in data.get("content", []):
        print(f'\n[content block] type = {block.get("type")}')
        print(json.dumps(block, ensure_ascii=False, indent=2))
    tb = next((b for b in data.get("content", []) if b.get("type") == "tool_use"), None)
    if tb:
        print("\n>>> 解读：模型没有执行任何代码，它只是在请求你调用一个函数：")
        print(f'    name : {tb["name"]}')
        print(f'    input: {json.dumps(tb["input"], ensure_ascii=False)}  <- 模型生成的"实参"')
        print(f'    id   : {tb["id"]}  <- 下一轮把 tool_result 带上这个 id 发回去')


def show_openai(data: dict) -> None:
    choice = data["choices"][0]
    print("=" * 64)
    print("finish_reason =", choice.get("finish_reason"), "  <- OpenAI 格式里的等价物：tool_calls")
    print("=" * 64)
    print(json.dumps(choice["message"], ensure_ascii=False, indent=2))


def main() -> None:
    token = get_access_token()

    # ---- 首选：Moonshot 的 Anthropic 兼容端点（能看到 stop_reason / tool_use）----
    url = "https://api.moonshot.cn/anthropic/v1/messages"
    request_body = {
        "model": MODEL,
        "max_tokens": 1024,
        "tools": [TOOL],
        "messages": [{"role": "user", "content": PROMPT}],
    }
    print(">>> 你发出去的完整请求体（prompt 只是 messages 里的一条）：")
    print(json.dumps(request_body, ensure_ascii=False, indent=2))
    print(f"\nPOST {url}")
    status, data = post(
        url,
        headers={
            "x-api-key": token,
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
        },
        json_body=request_body,
    )
    if status == 200:
        print("\n>>> 返回的完整原始响应：")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print()
        show_anthropic(data)
        return
    print(f"[fallback] Anthropic 端点 HTTP {status}: {json.dumps(data, ensure_ascii=False)[:300]}")

    # ---- 兜底：OpenAI 兼容端点（同样的概念，字段名叫 finish_reason / tool_calls）----
    url = "https://api.moonshot.cn/v1/chat/completions"
    print(f"\nPOST {url}  model={MODEL}\n")
    status, data = post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json_body={
            "model": MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": PROMPT}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": TOOL["name"],
                    "description": TOOL["description"],
                    "parameters": TOOL["input_schema"],
                },
            }],
        },
    )
    if status != 200:
        sys.exit(f"HTTP {status}: {json.dumps(data, ensure_ascii=False)[:500]}")
    show_openai(data)


# ---------- 闭环的另一半（先不跑，看看长什么样） ----------
# 你在本地"执行"函数得到结果后，再发第二次请求，messages 追加两条：
#
#   {"role": "assistant", "content": data["content"]},          # 原样带回 tool_use block
#   {"role": "user", "content": [{
#       "type": "tool_result",
#       "tool_use_id": tb["id"],                                 # 与上面的 id 配对
#       "content": "东京，晴，26°C，湿度 60%",                     # 你函数的返回
#   }]},
#
# 这次模型会基于 tool_result 生成自然语言回答，stop_reason 变成 "end_turn"。
# 所谓 agent loop，就是把"调用 -> tool_use -> 执行 -> tool_result -> 再调用"写成循环。

if __name__ == "__main__":
    main()
