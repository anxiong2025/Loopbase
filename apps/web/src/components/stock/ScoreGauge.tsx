"use client";

import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { ChartNoAxesCombined, Flame, Gem, HeartPulse, ShieldCheck } from "lucide-react";
import type { SubScores } from "@/lib/types";

const SUB_LABELS: Record<keyof SubScores, string> = {
  fundamentals: "基本面",
  growth: "成长性",
  valuation: "估值合理性",
  sentiment: "市场情绪",
  risk: "风险控制",
};

function scoreColor(score: number) {
  if (score >= 75) return "#6b8f5e";
  if (score >= 50) return "#c98a3a";
  return "#b3554a";
}

export function ScoreGauge({ score, subScores }: { score: number; subScores: SubScores }) {
  const color = score >= 75 ? "#c48a1b" : scoreColor(score);
  const data = [{ name: "score", value: score, fill: color }];
  const icons = {
    fundamentals: ChartNoAxesCombined,
    growth: Flame,
    valuation: Gem,
    sentiment: HeartPulse,
    risk: ShieldCheck,
  };

  return (
    <div className="app-card rounded-xl p-4">
      <div className="mb-1 text-[13px] font-semibold">Agent 投资评分</div>
      <div className="grid items-center gap-1.5 sm:grid-cols-[116px_1fr]">
      <div className="relative mx-auto h-28 w-28">
        <RadialBarChart
          width={112}
          height={112}
          cx="50%"
          cy="50%"
          innerRadius="72%"
          outerRadius="100%"
          barSize={9}
          data={data}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "var(--border)" }} />
        </RadialBarChart>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tracking-tight text-foreground">
            {score}
          </span>
          <span className="text-[10px] text-muted-foreground">/100</span>
        </div>
      </div>

      <div className="w-full space-y-1.5">
        {(Object.keys(SUB_LABELS) as (keyof SubScores)[]).map((key) => {
          const Icon = icons[key];
          return (
            <div key={key} className="flex items-center justify-between text-[10px]">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Icon className="h-3 w-3" /> {SUB_LABELS[key]}
              </span>
              <span className="font-semibold" style={{ color: scoreColor(subScores[key]) }}>
                {subScores[key]} <span className="font-normal text-muted-foreground">/100</span>
              </span>
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
}
