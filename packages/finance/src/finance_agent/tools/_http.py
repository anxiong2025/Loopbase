"""工具共用的 HTTP 请求辅助（仅标准库）。"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request


def fetch_json(url: str, timeout: float = 15.0) -> dict:
    """GET 一个 JSON 接口；失败时抛出带原因描述的异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"接口请求失败：{exc}") from exc


def fetch_json_with_crumb(url: str, timeout: float = 15.0) -> dict:
    """请求需要 cookie+crumb 鉴权的 Yahoo 接口（如 quoteSummary）。

    流程：先访问 fc.yahoo.com 种下会话 cookie，再用同一会话取 crumb，
    最后带 crumb 请求目标接口。
    """
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        opener.open(
            urllib.request.Request("https://fc.yahoo.com", headers=headers),
            timeout=timeout,
        )
        crumb = (
            opener.open(
                urllib.request.Request(
                    "https://query1.finance.yahoo.com/v1/test/getcrumb",
                    headers=headers,
                ),
                timeout=timeout,
            )
            .read()
            .decode()
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Yahoo 鉴权（cookie/crumb）失败：{exc}") from exc

    separator = "&" if "?" in url else "?"
    req = urllib.request.Request(
        f"{url}{separator}crumb={urllib.parse.quote(crumb)}",
        headers=headers,
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"接口请求失败：{exc}") from exc
