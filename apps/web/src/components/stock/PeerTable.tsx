"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { fetchPeers } from "@/lib/api";
import type { StockOverview } from "@/lib/types";

const DEFAULT_PEER_GROUPS: Record<string, string[]> = {
  NVDA: ["NVDA", "AMD", "INTC", "AVGO"],
  AMD: ["AMD", "NVDA", "INTC", "QCOM"],
  INTC: ["INTC", "AMD", "NVDA", "TXN"],
  AAPL: ["AAPL", "MSFT", "GOOGL", "SSNLF"],
  MSFT: ["MSFT", "AAPL", "GOOGL", "AMZN"],
  GOOGL: ["GOOGL", "META", "MSFT", "AMZN"],
  META: ["META", "GOOGL", "SNAP", "PINS"],
  TSLA: ["TSLA", "GM", "F", "RIVN"],
  AMZN: ["AMZN", "WMT", "BABA", "SHOP"],
};

function fmt(v: number | null | undefined, kind: "x" | "pct" | "cap" = "x") {
  if (v === null || v === undefined) return "—";
  if (kind === "pct") return `${(v * 100).toFixed(1)}%`;
  if (kind === "cap") {
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}万亿`;
    if (Math.abs(v) >= 1e8) return `$${(v / 1e8).toFixed(0)}亿`;
    return `$${v.toLocaleString()}`;
  }
  return v.toFixed(1);
}

export function PeerTable({ ticker }: { ticker: string }) {
  const initialList = DEFAULT_PEER_GROUPS[ticker] ?? [ticker];
  const [tickersInput, setTickersInput] = useState(initialList.join(", "));
  const [peers, setPeers] = useState<StockOverview[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(list: string[]) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPeers(list);
      setPeers(res.peers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchPeers(initialList.slice(0, 4));
        if (!cancelled) setPeers(res.peers);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app-card rounded-xl p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold">同行对比</div>
        <div className="flex items-center gap-2">
          <Input
            value={tickersInput}
            onChange={(e) => setTickersInput(e.target.value)}
            className="h-8 w-56 text-xs"
            placeholder="逗号分隔，如 NVDA, AMD, INTC"
          />
          <Button
            size="sm"
            variant="outline"
            className="h-8 gap-1.5 text-xs"
            onClick={() =>
              load(
                tickersInput
                  .split(",")
                  .map((t) => t.trim().toUpperCase())
                  .filter(Boolean)
                  .slice(0, 6),
              )
            }
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> 对比
          </Button>
        </div>
      </div>

      {error && <div className="text-xs text-destructive">{error}</div>}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-xs">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">代码</th>
              <th className="py-2 pr-3 font-medium">市值</th>
              <th className="py-2 pr-3 font-medium">PE (TTM)</th>
              <th className="py-2 pr-3 font-medium">PS (TTM)</th>
              <th className="py-2 pr-3 font-medium">净利率</th>
              <th className="py-2 pr-3 font-medium">营收同比</th>
            </tr>
          </thead>
          <tbody>
            {(peers ?? []).map((p) => (
              <tr
                key={p.symbol}
                className={`border-b border-border/60 ${p.symbol === ticker ? "bg-secondary/50" : ""}`}
              >
                <td className="py-2 pr-3 font-semibold">{p.symbol}</td>
                {p.error ? (
                  <td colSpan={5} className="py-2 pr-3 text-muted-foreground">
                    {p.warnings?.[0] ?? "数据暂不可用"}
                  </td>
                ) : (
                  <>
                    <td className="py-2 pr-3">{fmt(p.marketCap, "cap")}</td>
                    <td className="py-2 pr-3">{fmt(p.peTTM)}</td>
                    <td className="py-2 pr-3">{fmt(p.psTTM)}</td>
                    <td className="py-2 pr-3">{fmt(p.profitMargin, "pct")}</td>
                    <td className="py-2 pr-3">{fmt(p.revenueGrowthYoY, "pct")}</td>
                  </>
                )}
              </tr>
            ))}
            {!peers && loading && (
              <tr>
                <td colSpan={6} className="py-4 text-center text-muted-foreground">
                  加载中…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        数据源：Alpha Vantage OVERVIEW，免费额度每日 25 次请求，同行越多消耗越快。
      </p>
    </div>
  );
}
