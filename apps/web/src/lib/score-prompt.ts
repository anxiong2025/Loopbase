import type { ScoreResult } from "./types";

/**
 * “评分”不是一个单独的模型/接口——就是同一个 ReAct 循环，
 * 只是我们在问题里明确要求它查完数据后，把结论整理成一段结构化 JSON。
 * 复用 /analyze/stream，不新增后端能力。
 */
export function buildScorePrompt(ticker: string): string {
  return [
    `对 ${ticker} 做一次投资研报分析。请先调用工具获取最新股价、核心财务指标、利润表和新闻情绪，`,
    `然后用 2-4 句话写出核心投资论点。`,
    `如果部分数据缺失或接口限流，只能用一句简短的数据说明提及一次；不要在摘要、正文、结论、注释或免责声明里重复说明。`,
    ``,
    `最后必须另起一段，输出且仅输出一个 \`\`\`json 代码块（不要在代码块前后加任何多余文字），严格符合下面的结构：`,
    `{`,
    `  "score": 0到100的整数，你对该股票的综合投资评分,`,
    `  "rating": "强力看多" | "看多" | "中性" | "看空" | "强力看空",`,
    `  "subScores": { "fundamentals": 0-100, "growth": 0-100, "valuation": 0-100, "sentiment": 0-100, "risk": 0-100 },`,
    `  "targetPrice": 数字或 null（你估计的合理目标价，美元）,`,
    `  "thesis": "核心论点，2-4句话，中文",`,
    `  "bullPoints": ["核心利好催化剂1", "核心利好催化剂2", "核心利好催化剂3"],`,
    `  "bearPoints": ["下行风险1", "下行风险2", "下行风险3"]`,
    `}`,
  ].join("\n");
}

export function parseScoreResult(finalAnswer: string | null): ScoreResult | null {
  if (!finalAnswer) return null;
  const match = finalAnswer.match(/```json\s*([\s\S]*?)```/);
  const raw = match ? match[1] : finalAnswer;
  try {
    const parsed = JSON.parse(raw.trim());
    if (typeof parsed.score !== "number" || !parsed.subScores) return null;
    return parsed as ScoreResult;
  } catch {
    return null;
  }
}

/** 把最终回答里的 JSON 代码块去掉，只留给人看的叙述部分。 */
export function stripScoreJson(finalAnswer: string | null): string {
  if (!finalAnswer) return "";
  return finalAnswer.replace(/```json\s*[\s\S]*?```/, "").trim();
}
