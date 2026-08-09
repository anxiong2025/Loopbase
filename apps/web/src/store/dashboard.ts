import { create } from "zustand";
import type { Citation, ScoreResult, StockOverview, StreamEvent } from "@/lib/types";

export type RunStep = {
  id: string;
  kind: "think" | "tool" | "final" | "warn";
  label: string;
  status: "pending" | "done" | "error";
  caption?: string;
};

type DashboardState = {
  ticker: string | null;
  overview: StockOverview | null;
  overviewError: string | null;
  overviewLoading: boolean;

  citations: Citation[] | null;
  citationsError: string | null;
  citationsLoading: boolean;

  score: ScoreResult | null;
  scoreNarrative: string;
  scoreError: string | null;
  scoreLoading: boolean;
  scoreSteps: RunStep[];
  scoreGeneratedAt: string | null;
  scoreCacheHit: boolean;

  setTicker: (ticker: string) => void;
  setOverview: (overview: StockOverview | null, error?: string | null) => void;
  setOverviewLoading: (loading: boolean) => void;
  setCitations: (citations: Citation[] | null, error?: string | null) => void;
  setCitationsLoading: (loading: boolean) => void;
  setScoreLoading: (loading: boolean) => void;
  setScoreResult: (
    score: ScoreResult | null,
    narrative: string,
    error?: string | null,
    meta?: { generatedAt?: string | null; cacheHit?: boolean },
  ) => void;
  resetScoreSteps: () => void;
  applyScoreEvent: (evt: StreamEvent) => void;
};

let stepSeq = 0;
function stepId() {
  stepSeq += 1;
  return `step-${stepSeq}`;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  ticker: null,
  overview: null,
  overviewError: null,
  overviewLoading: false,

  citations: null,
  citationsError: null,
  citationsLoading: false,

  score: null,
  scoreNarrative: "",
  scoreError: null,
  scoreLoading: false,
  scoreSteps: [],
  scoreGeneratedAt: null,
  scoreCacheHit: false,

  setTicker: (ticker) => set({ ticker: ticker.toUpperCase() }),
  setOverview: (overview, error = null) => set({ overview, overviewError: error }),
  setOverviewLoading: (overviewLoading) => set({ overviewLoading }),
  setCitations: (citations, error = null) => set({ citations, citationsError: error }),
  setCitationsLoading: (citationsLoading) => set({ citationsLoading }),
  setScoreLoading: (scoreLoading) => set({ scoreLoading }),
  setScoreResult: (score, narrative, error = null, meta) =>
    set({
      score,
      scoreNarrative: narrative,
      scoreError: error,
      scoreGeneratedAt: meta?.generatedAt ?? null,
      scoreCacheHit: meta?.cacheHit ?? false,
    }),
  resetScoreSteps: () => set({ scoreSteps: [] }),

  applyScoreEvent: (evt) => {
    const steps = get().scoreSteps;
    const upsert = (next: RunStep[]) => set({ scoreSteps: next });

    switch (evt.kind) {
      case "turn.start":
        upsert([
          ...steps,
          { id: stepId(), kind: "think", label: `第 ${evt.turn} 轮 · 分析中`, status: "pending" },
        ]);
        return;
      case "model.response": {
        const next = [...steps];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].kind === "think" && next[i].status === "pending") {
            next[i] = { ...next[i], status: "done" };
            break;
          }
        }
        upsert(next);
        return;
      }
      case "tool.call":
        upsert([
          ...steps,
          { id: stepId(), kind: "tool", label: evt.name, status: "pending" },
        ]);
        return;
      case "tool.result": {
        const next = [...steps];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].kind === "tool" && next[i].status === "pending") {
            next[i] = {
              ...next[i],
              status: "done",
              caption: evt.result.length > 60 ? evt.result.slice(0, 60) + "…" : evt.result,
            };
            break;
          }
        }
        upsert(next);
        return;
      }
      case "tool.error": {
        const next = [...steps];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].kind === "tool" && next[i].status === "pending") {
            next[i] = { ...next[i], status: "error", caption: evt.error };
            break;
          }
        }
        upsert(next);
        return;
      }
      case "turn.final":
        upsert([...steps, { id: stepId(), kind: "final", label: "生成综合研报", status: "done" }]);
        return;
      case "turn.max_turns":
        upsert([...steps, { id: stepId(), kind: "warn", label: "已达最大轮数上限", status: "error" }]);
        return;
      default:
        return;
    }
  },
}));
