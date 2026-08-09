export type StockOverview = {
  symbol: string;
  warnings: string[];
  price?: number | null;
  change?: number | null;
  changePercent?: number | null;
  latestTradingDay?: string | null;
  name?: string | null;
  sector?: string | null;
  industry?: string | null;
  marketCap?: number | null;
  peTTM?: number | null;
  peForward?: number | null;
  psTTM?: number | null;
  pbRatio?: number | null;
  evToEbitda?: number | null;
  profitMargin?: number | null;
  operatingMargin?: number | null;
  revenueGrowthYoY?: number | null;
  earningsGrowthYoY?: number | null;
  dividendYield?: number | null;
  analystTargetPrice?: number | null;
  week52Low?: number | null;
  week52High?: number | null;
  beta?: number | null;
  cik?: string | null;
  error?: boolean;
};

export type Citation = {
  concept: string;
  label: string;
  value: number;
  unit: string;
  fiscalPeriodEnd: string | null;
  fiscalYear: number | null;
  fiscalPeriod: string | null;
  form: string | null;
  filed: string | null;
  accessionNumber: string | null;
  sourceUrl: string | null;
};

export type CitationsResponse = {
  symbol: string;
  cik: string;
  companyName: string;
  citations: Citation[];
};

export type PeersResponse = {
  peers: StockOverview[];
};

export type SubScores = {
  fundamentals: number;
  growth: number;
  valuation: number;
  sentiment: number;
  risk: number;
};

export type ScoreResult = {
  score: number;
  rating: string;
  subScores: SubScores;
  targetPrice: number | null;
  thesis: string;
  bullPoints: string[];
  bearPoints: string[];
};

export type StreamEvent =
  | { kind: "turn.start"; turn: number; message_count: number }
  | {
      kind: "model.response";
      turn: number;
      finish_reason: string;
      usage: { prompt_tokens?: number; completion_tokens?: number } | null;
      content: string;
      tool_calls: { id: string; name: string; arguments: Record<string, unknown> }[];
    }
  | { kind: "tool.call"; turn: number; name: string; arguments: Record<string, unknown> }
  | { kind: "tool.result"; turn: number; name: string; result: string }
  | { kind: "tool.error"; turn: number; name: string; error: string }
  | { kind: "turn.final"; turn: number; answer: string }
  | { kind: "turn.max_turns"; turns: number }
  | {
      kind: "done";
      final_answer: string | null;
      turns: number;
      stopped_by: string;
      tool_calls_executed: string[];
      generated_at?: string;
      cache_hit?: boolean;
    }
  | { kind: "error"; message: string };
