"""SEC EDGAR 溯源：把结论关联到真实公开文件，而不是模型自己的转述。

数据源（均免费、无需 key，只需要一个能识别身份的 User-Agent）：
- 股票代码 -> CIK 映射：https://www.sec.gov/files/company_tickers.json
- 结构化财务事实（XBRL）：https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

思路：不去解析财报全文找"这句话对应哪句原文"（那是更复杂的 NLP 问题），
而是把关键财务科目的官方申报数值连同它所在的那份 10-Q/10-K 的真实链接
一起亮出来——用户点开就是 SEC.gov 上那份文件本身，不是模型编的。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_USER_AGENT = "Loopbase-Demo/0.1 (educational project; contact: no-reply@loopbase.local)"

_TICKER_MAP_TTL_SECONDS = 24 * 3600
_FACTS_TTL_SECONDS = 6 * 3600

_ticker_map_cache: tuple[float, dict[str, dict]] | None = None
_facts_cache: dict[str, tuple[float, dict]] = {}

# 仪表盘上展示的核心报表科目（US-GAAP 分类法），(concept, 中文标签)
_CONCEPTS: list[tuple[str, str]] = [
    ("Revenues", "营业收入"),
    ("NetIncomeLoss", "净利润"),
    ("GrossProfit", "毛利润"),
    ("EarningsPerShareDiluted", "稀释每股收益"),
    ("Assets", "总资产"),
    ("Liabilities", "总负债"),
]


def _fetch_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"SEC EDGAR 请求失败：{exc}") from exc


def _cik10(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


def _load_ticker_map() -> dict[str, dict]:
    global _ticker_map_cache
    now = time.monotonic()
    if _ticker_map_cache is None or now - _ticker_map_cache[0] > _TICKER_MAP_TTL_SECONDS:
        raw = _fetch_json(_TICKERS_URL)
        table = {entry["ticker"].upper(): entry for entry in raw.values()}
        _ticker_map_cache = (now, table)
    return _ticker_map_cache[1]


def resolve(symbol: str) -> dict[str, Any]:
    """股票代码 -> CIK + 公司名。找不到就说明这不是 SEC 报备主体（如非美股 ADR 的部分情况）。"""
    entry = _load_ticker_map().get(symbol.upper().strip())
    if entry is None:
        raise RuntimeError(f"SEC EDGAR 未收录股票代码 {symbol}")
    return {
        "cik": _cik10(entry["cik_str"]),
        "cikInt": int(entry["cik_str"]),
        "title": entry["title"],
    }


def _company_facts(cik10: str) -> dict:
    now = time.monotonic()
    cached = _facts_cache.get(cik10)
    if cached and now - cached[0] < _FACTS_TTL_SECONDS:
        return cached[1]
    data = _fetch_json(_FACTS_URL.format(cik=cik10))
    _facts_cache[cik10] = (now, data)
    return data


def _latest_entry(node: dict) -> tuple[str, list[dict]] | None:
    units = node.get("units") or {}
    for unit_key in ("USD", "USD/shares"):
        entries = units.get(unit_key)
        if entries:
            return unit_key, entries
    return None


def citations(symbol: str) -> dict[str, Any]:
    """返回 {symbol} 的可溯源财务事实：科目、数值、来源财报、SEC.gov 原文链接。"""
    company = resolve(symbol)
    facts = _company_facts(company["cik"])
    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}

    items: list[dict[str, Any]] = []
    for concept, label in _CONCEPTS:
        node = us_gaap.get(concept)
        if not node:
            continue
        found = _latest_entry(node)
        if not found:
            continue
        unit_key, entries = found

        authoritative = [e for e in entries if e.get("form") in ("10-Q", "10-K")]
        pool = authoritative or entries
        latest = max(pool, key=lambda e: e.get("end") or "")

        accession = latest.get("accn", "")
        accession_nodashes = accession.replace("-", "")
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{company['cikInt']}/"
            f"{accession_nodashes}/{accession}-index.htm"
            if accession
            else None
        )

        items.append(
            {
                "concept": concept,
                "label": label,
                "value": latest.get("val"),
                "unit": unit_key,
                "fiscalPeriodEnd": latest.get("end"),
                "fiscalYear": latest.get("fy"),
                "fiscalPeriod": latest.get("fp"),
                "form": latest.get("form"),
                "filed": latest.get("filed"),
                "accessionNumber": accession or None,
                "sourceUrl": source_url,
            }
        )

    return {
        "symbol": symbol.upper(),
        "cik": company["cik"],
        "companyName": facts.get("entityName") or company["title"],
        "citations": items,
    }
