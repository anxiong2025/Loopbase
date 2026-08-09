"use client";

import { BarChart3, CircleDollarSign, FileText, Gauge, Info, Sparkles } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ThesisCard } from "@/components/stock/ThesisCard";
import { PeerTable } from "@/components/stock/PeerTable";
import type { Citation, ScoreResult, StockOverview, SubScores } from "@/lib/types";

type Props = {
  ticker: string;
  overview: StockOverview;
  score: ScoreResult;
  narrative: string;
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
};

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function multiple(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}x`;
}

export function ResearchWorkspace(props: Props) {
  const { ticker, overview, score, narrative, citations, onCitationClick } = props;

  return (
    <Tabs defaultValue="thesis" className="min-w-0 gap-2">
      <TabsList
        variant="line"
        aria-label="研报分析维度"
        className="h-9 w-full justify-between gap-2 overflow-hidden border-b border-border px-0 sm:justify-start sm:gap-6"
      >
        <TabsTrigger value="thesis" className="h-9 flex-none px-1 text-xs data-active:text-primary after:bg-primary sm:text-sm">
          核心论点
        </TabsTrigger>
        <TabsTrigger value="financials" className="h-9 flex-none px-1 text-xs data-active:text-primary after:bg-primary sm:text-sm">
          财务分析
        </TabsTrigger>
        <TabsTrigger value="valuation" className="h-9 flex-none px-1 text-xs data-active:text-primary after:bg-primary sm:text-sm">
          DCF 估值
        </TabsTrigger>
        <TabsTrigger value="sentiment" className="h-9 flex-none px-1 text-xs data-active:text-primary after:bg-primary sm:text-sm">
          多空博弈
        </TabsTrigger>
      </TabsList>

      <TabsContent value="thesis">
        <ThesisCard
          score={score}
          narrative={narrative}
          citations={citations}
          onCitationClick={onCitationClick}
        />
      </TabsContent>

      <TabsContent value="financials" className="space-y-4">
        <FinancialSnapshot overview={overview} citations={citations} onCitationClick={onCitationClick} />
        <PeerTable key={`peers-${ticker}`} ticker={ticker} />
      </TabsContent>

      <TabsContent value="valuation">
        <ValuationModel overview={overview} score={score} />
      </TabsContent>

      <TabsContent value="sentiment">
        <SentimentPanel score={score} />
      </TabsContent>
    </Tabs>
  );
}

function FinancialSnapshot({
  overview,
  citations,
  onCitationClick,
}: {
  overview: StockOverview;
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
}) {
  const metrics = [
    { label: "营收同比", value: percent(overview.revenueGrowthYoY), tone: "positive" },
    { label: "盈利同比", value: percent(overview.earningsGrowthYoY), tone: "positive" },
    { label: "净利率", value: percent(overview.profitMargin), tone: "neutral" },
    { label: "营业利润率", value: percent(overview.operatingMargin), tone: "neutral" },
    { label: "市销率 (TTM)", value: multiple(overview.psTTM), tone: "neutral" },
    { label: "EV / EBITDA", value: multiple(overview.evToEbitda), tone: "neutral" },
  ];

  return (
    <div className="app-card rounded-xl p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[15px] font-semibold">
            <BarChart3 className="h-4 w-4 text-primary" /> 财务质量快照
          </div>
          <p className="mt-1 text-xs text-muted-foreground">增长、盈利能力与估值倍数的核心观察</p>
        </div>
        <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">TTM / 最新财年</span>
      </div>
      <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map((metric) => (
          <div key={metric.label} className="bg-card px-4 py-4">
            <div className="text-[11px] text-muted-foreground">{metric.label}</div>
            <div className={`mt-1 text-xl font-semibold ${metric.tone === "positive" ? "text-[#168653]" : ""}`}>
              {metric.value}
            </div>
          </div>
        ))}
      </div>
      {citations.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-muted-foreground">SEC 原始数据：</span>
          {citations.slice(0, 4).map((citation) => (
            <button
              key={citation.concept}
              type="button"
              onClick={() => onCitationClick(citation)}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2.5 py-1 text-[10px] transition-colors hover:border-primary hover:text-primary"
            >
              <FileText className="h-3 w-3" /> {citation.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ValuationModel({ overview, score }: { overview: StockOverview; score: ScoreResult }) {
  const current = overview.price ?? 0;
  const target = score.targetPrice ?? overview.analystTargetPrice ?? current;
  const downside = current * 0.82;
  const upside = target * 1.12;
  const max = Math.max(upside, target, current, 1);
  const currentPosition = Math.min(100, Math.max(0, (current / max) * 100));
  const targetPosition = Math.min(100, Math.max(0, (target / max) * 100));

  return (
    <div className="app-card rounded-xl p-5 lg:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[15px] font-semibold">
            <CircleDollarSign className="h-4 w-4 text-primary" /> DCF 情景估值
          </div>
          <p className="mt-1 text-xs text-muted-foreground">基于 Agent 目标价展示估值区间与安全边际</p>
        </div>
        <button type="button" title="情景值用于辅助判断，不构成投资建议">
          <Info className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>

      <div className="mt-8 rounded-xl bg-muted/55 px-5 py-7">
        <div className="relative h-12">
          <div className="absolute left-0 right-0 top-5 h-2 rounded-full bg-gradient-to-r from-[#c7473c] via-[#d8b25e] to-[#168653]" />
          <div className="absolute top-2 h-8 w-px bg-foreground" style={{ left: `${currentPosition}%` }}>
            <span className="absolute -left-10 -top-7 w-20 text-center text-[10px] text-muted-foreground">现价</span>
          </div>
          <div className="absolute top-1 h-10 w-px bg-primary" style={{ left: `${targetPosition}%` }}>
            <span className="absolute -left-10 -top-7 w-20 text-center text-[10px] font-medium text-primary">Agent 目标</span>
          </div>
        </div>
        <div className="mt-2 grid grid-cols-4 text-center">
          <Scenario label="压力情景" value={downside} />
          <Scenario label="当前价格" value={current} />
          <Scenario label="基准目标" value={target} highlight />
          <Scenario label="乐观情景" value={upside} />
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <Assumption label="折现率 WACC" value="9.2%" />
        <Assumption label="永续增长率" value="3.0%" />
        <Assumption label="预测周期" value="5 年" />
      </div>
    </div>
  );
}

function Scenario({ label, value, highlight = false }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${highlight ? "text-primary" : ""}`}>${value.toFixed(2)}</div>
    </div>
  );
}

function Assumption({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

function SentimentPanel({ score }: { score: ScoreResult }) {
  const rows: { key: keyof SubScores; label: string }[] = [
    { key: "fundamentals", label: "基本面支撑" },
    { key: "growth", label: "成长动能" },
    { key: "valuation", label: "估值吸引力" },
    { key: "sentiment", label: "市场情绪" },
    { key: "risk", label: "风险韧性" },
  ];

  return (
    <div className="app-card rounded-xl p-5 lg:p-6">
      <div className="flex items-center gap-2 text-[15px] font-semibold">
        <Gauge className="h-4 w-4 text-primary" /> 多空力量拆解
      </div>
      <p className="mt-1 text-xs text-muted-foreground">将 Agent 的五维评分映射为可比较的信号强度</p>
      <div className="mt-6 space-y-5">
        {rows.map((row) => {
          const value = score.subScores[row.key];
          return (
            <div key={row.key} className="grid grid-cols-[90px_1fr_42px] items-center gap-3">
              <span className="text-xs text-muted-foreground">{row.label}</span>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#d8ad55] to-[#b77b09] transition-all duration-500"
                  style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                />
              </div>
              <span className="text-right text-xs font-semibold">{value}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-7 rounded-lg border border-primary/20 bg-secondary/40 px-4 py-3 text-xs leading-5 text-secondary-foreground">
        <Sparkles className="mr-1 inline h-3.5 w-3.5" />
        当前综合评级为“{score.rating}”。建议结合估值标签中的安全边际与下行风险共同判断。
      </div>
    </div>
  );
}
