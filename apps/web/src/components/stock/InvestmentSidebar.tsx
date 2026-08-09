"use client";

import { ArrowRight, Info } from "lucide-react";
import { ScoreGauge } from "@/components/stock/ScoreGauge";
import type { ScoreResult, StockOverview } from "@/lib/types";

export function InvestmentSidebar({ overview, score }: { overview: StockOverview; score: ScoreResult }) {
  const current = overview.price ?? 0;
  const target = score.targetPrice ?? overview.analystTargetPrice ?? 0;
  const upside = current > 0 && target > 0 ? ((target - current) / current) * 100 : null;

  return (
    <aside className="min-w-0 space-y-2 xl:grid xl:h-full xl:grid-rows-[auto_auto_minmax(0,1fr)] xl:gap-2 xl:space-y-0">
      <ScoreGauge score={score.score} subScores={score.subScores} />
      <div className="app-card flex h-full flex-col rounded-xl p-3">
        <div className="flex items-center gap-1.5 text-[13px] font-semibold">
          估值空间
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="mt-2 flex items-end justify-between">
          <div>
            <div className="text-[10px] text-muted-foreground">现价</div>
            <div className="text-sm font-semibold">{current ? `$${current.toFixed(2)}` : "—"}</div>
          </div>
          <div className="mb-2 flex min-w-16 flex-1 items-center px-3">
            <span className="h-1.5 w-1.5 rounded-full bg-foreground" />
            <span className="h-px flex-1 bg-gradient-to-r from-foreground via-primary to-primary" />
            <ArrowRight className="h-3.5 w-3.5 text-primary" />
          </div>
          <div className="text-right">
            <div className="text-[10px] text-muted-foreground">目标价</div>
            <div className="text-sm font-semibold text-primary">{target ? `$${target.toFixed(2)}` : "—"}</div>
          </div>
        </div>
        <div className={`text-center text-xs font-semibold ${upside !== null && upside >= 0 ? "text-[#168653]" : "text-destructive"}`}>
          {upside !== null ? `${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%` : "—"}
        </div>
      </div>

      <div className="app-card flex h-full flex-col rounded-xl p-3">
        <div className="flex items-center gap-1.5 text-[13px] font-semibold">
          关键指标
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="flex flex-1 items-center">
          <div className="grid w-full grid-cols-3 divide-x divide-border">
            <MiniMetric label="营收增长" value={asPercent(overview.revenueGrowthYoY)} points="2,24 12,20 22,15 32,17 42,11 52,8 62,4" />
            <MiniMetric label="毛利趋势" value={asPercent(overview.profitMargin)} points="2,24 12,16 22,18 32,10 42,12 52,7 62,5" />
            <MiniMetric label="盈利增长" value={asPercent(overview.earningsGrowthYoY)} points="2,23 12,18 22,14 32,11 42,13 52,7 62,4" />
          </div>
        </div>
      </div>
    </aside>
  );
}

function asPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function MiniMetric({ label, value, points }: { label: string; value: string; points: string }) {
  const negative = value.startsWith("-");
  return (
    <div className="px-2 first:pl-0 last:pr-0">
      <div className="truncate text-[9px] text-muted-foreground">{label}</div>
      <div className={`mt-0.5 text-[11px] font-semibold ${negative ? "text-destructive" : "text-[#168653]"}`}>{value}</div>
      <svg viewBox="0 0 64 28" className="mt-1 h-5 w-full" aria-hidden="true">
        <path d="M1 26H63" stroke="var(--border)" strokeWidth="1" />
        <polyline points={points} fill="none" stroke={negative ? "#c7473c" : "#168653"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}
