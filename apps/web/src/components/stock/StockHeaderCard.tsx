"use client";

import { Badge } from "@/components/ui/badge";
import { Activity, Cpu } from "lucide-react";
import type { ScoreResult, StockOverview } from "@/lib/types";

function fmtMoney(v: number | null | undefined, opts: { compact?: boolean } = {}) {
  if (v === null || v === undefined) return "—";
  if (opts.compact) {
    const abs = Math.abs(v);
    if (abs >= 1e12) return `$${(v / 1e12).toFixed(2)}万亿`;
    if (abs >= 1e8) return `$${(v / 1e8).toFixed(2)}亿`;
    return `$${v.toLocaleString()}`;
  }
  return `$${v.toFixed(2)}`;
}

function ratingTone(rating: string) {
  if (rating.includes("强力看多") || rating.includes("看多")) return "bg-[#eaf1e6] text-[#4f7a5c]";
  if (rating.includes("强力看空") || rating.includes("看空")) return "bg-[#f6e8e5] text-[#a8493b]";
  return "bg-secondary text-secondary-foreground";
}

export function StockHeaderCard({
  overview,
  score,
  reportMeta,
}: {
  overview: StockOverview;
  score: ScoreResult | null;
  reportMeta?: React.ReactNode;
}) {
  const upside =
    score?.targetPrice && overview.price
      ? ((score.targetPrice - overview.price) / overview.price) * 100
      : null;
  const changeUp = (overview.change ?? 0) >= 0;

  return (
    <div className="app-card rounded-xl p-3 lg:px-4 lg:py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#191916] text-[#c7e50f] shadow-sm">
            {overview.symbol === "NVDA" ? <Cpu className="h-5 w-5" /> : <Activity className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight">{overview.name ?? overview.symbol}</h1>
              <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                {overview.symbol}
              </span>
              {score && (
                <Badge className={`h-5 border-none px-2 text-[10px] ${ratingTone(score.rating)}`}>
                  {score.rating}
                </Badge>
              )}
            </div>
            {overview.sector && (
              <div className="mt-0.5 text-[10px] text-muted-foreground">
                {overview.sector} · {overview.industry}
              </div>
            )}
          </div>
        </div>
        <div className="text-right text-[10px] text-muted-foreground">
          <div className="mb-0.5 inline-flex items-center gap-1.5 text-foreground/75">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#168653] opacity-40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[#168653]" />
            </span>
            数据实时刷新
          </div>
          {overview.latestTradingDay && <div>更新于 {overview.latestTradingDay}</div>}
          {reportMeta}
          {overview.warnings.length > 0 && (
            <div title={overview.warnings.join("；")} className="mt-0.5 text-[9px] text-primary">
              部分数据缺失
            </div>
          )}
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 divide-x-0 divide-border/80 border-t border-border/70 pt-2 sm:grid-cols-5 sm:divide-x">
        <Metric label="最新价" value={fmtMoney(overview.price)}>
          {overview.change !== null && overview.change !== undefined && (
            <span className={changeUp ? "text-[#4f7a5c]" : "text-[#a8493b]"}>
              {changeUp ? "+" : ""}
              {overview.change?.toFixed(2)} ({overview.changePercent?.toFixed(2)}%)
            </span>
          )}
        </Metric>
        <Metric label="市值" value={fmtMoney(overview.marketCap, { compact: true })} />
        <Metric label="市盈率 (TTM)" value={overview.peTTM ? overview.peTTM.toFixed(1) : "—"} />
        <Metric
          label="Agent 目标价"
          value={score?.targetPrice ? fmtMoney(score.targetPrice) : "—"}
          highlight
        />
        <Metric
          label="上行空间"
          value={upside !== null ? `${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%` : "—"}
          tone={upside !== null ? (upside >= 0 ? "up" : "down") : undefined}
        />
      </div>

    </div>
  );
}

function Metric({
  label,
  value,
  children,
  highlight,
  tone,
}: {
  label: string;
  value: string;
  children?: React.ReactNode;
  highlight?: boolean;
  tone?: "up" | "down";
}) {
  return (
    <div className="min-w-0 py-1 sm:px-3.5 sm:first:pl-0 sm:last:pr-0">
      <div className="mb-0.5 text-[10px] text-muted-foreground">{label}</div>
      <div
        className={
          "truncate text-base font-semibold tracking-tight " +
          (highlight ? "text-primary" : tone === "up" ? "text-[#4f7a5c]" : tone === "down" ? "text-[#a8493b]" : "")
        }
      >
        {value}
      </div>
      {children && <div className="text-[10px] font-medium">{children}</div>}
    </div>
  );
}
