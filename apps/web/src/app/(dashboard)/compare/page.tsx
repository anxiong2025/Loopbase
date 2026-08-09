"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Scale } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { fetchPeers } from "@/lib/api";
import type { StockOverview } from "@/lib/types";

const DEFAULT_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"];

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

export default function ComparePage() {
  const [tickersInput, setTickersInput] = useState(DEFAULT_TICKERS.join(", "));
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
        const res = await fetchPeers(DEFAULT_TICKERS);
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
  }, []);

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 space-y-5 px-5 py-6">
      <div className="flex items-center gap-2">
        <Scale className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold">对比分析</h1>
      </div>

      <div className="rounded-2xl border border-border bg-card p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Input
            value={tickersInput}
            onChange={(e) => setTickersInput(e.target.value)}
            className="h-9 w-80 text-sm"
            placeholder="逗号分隔，如 NVDA, AMD, INTC"
          />
          <Button
            size="sm"
            className="gap-1.5"
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
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> 对比
          </Button>
        </div>

        {error && <div className="mb-3 text-sm text-destructive">{error}</div>}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2 pr-4 font-medium">代码</th>
                <th className="py-2 pr-4 font-medium">最新价</th>
                <th className="py-2 pr-4 font-medium">市值</th>
                <th className="py-2 pr-4 font-medium">PE (TTM)</th>
                <th className="py-2 pr-4 font-medium">PS (TTM)</th>
                <th className="py-2 pr-4 font-medium">净利率</th>
                <th className="py-2 pr-4 font-medium">营收同比</th>
              </tr>
            </thead>
            <tbody>
              {(peers ?? []).map((p) => (
                <tr key={p.symbol} className="border-b border-border/60">
                  <td className="py-2.5 pr-4 font-semibold">{p.symbol}</td>
                  {p.error ? (
                    <td colSpan={6} className="py-2.5 pr-4 text-xs text-muted-foreground">
                      {p.warnings?.[0] ?? "数据暂不可用"}
                    </td>
                  ) : (
                    <>
                      <td className="py-2.5 pr-4">{p.price ? `$${p.price.toFixed(2)}` : "—"}</td>
                      <td className="py-2.5 pr-4">{fmt(p.marketCap, "cap")}</td>
                      <td className="py-2.5 pr-4">{fmt(p.peTTM)}</td>
                      <td className="py-2.5 pr-4">{fmt(p.psTTM)}</td>
                      <td className="py-2.5 pr-4">{fmt(p.profitMargin, "pct")}</td>
                      <td className="py-2.5 pr-4">{fmt(p.revenueGrowthYoY, "pct")}</td>
                    </>
                  )}
                </tr>
              ))}
              {!peers && loading && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-muted-foreground">
                    加载中…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          价格数据源：Yahoo Finance（免费，无每日限额）。市值/PE/利润率等基本面数据源：Alpha
          Vantage（免费额度每日 25 次请求）。
        </p>
      </div>
    </main>
  );
}
