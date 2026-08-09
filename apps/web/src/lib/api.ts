import type { CitationsResponse, PeersResponse, StockOverview, StreamEvent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail ?? `请求失败：${res.status}`);
  }
  return data as T;
}

export function fetchOverview(ticker: string): Promise<StockOverview> {
  return getJson(`/stock/${encodeURIComponent(ticker)}/overview`);
}

export function fetchCitations(ticker: string): Promise<CitationsResponse> {
  return getJson(`/stock/${encodeURIComponent(ticker)}/citations`);
}

export function fetchPeers(tickers: string[]): Promise<PeersResponse> {
  return getJson(`/stock/peers?tickers=${encodeURIComponent(tickers.join(","))}`);
}

/**
 * 消费 /analyze/stream 的 SSE 输出。每解析出一个事件就回调一次；
 * 遇到 done/error 会在回调后自然结束（生成器 return）。
 */
export async function* streamAnalysis(
  question: string,
  maxTurns = 6,
  signal?: AbortSignal,
  forceRefresh = false,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_BASE}/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, max_turns: maxTurns, force_refresh: forceRefresh }),
    signal,
  });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? `请求失败：${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const evt = JSON.parse(line.slice(6)) as StreamEvent;
      yield evt;
      if (evt.kind === "done" || evt.kind === "error") return;
    }
  }
}
