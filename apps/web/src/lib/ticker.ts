const COMPANY_TICKERS: Record<string, string> = {
  APPLE: "AAPL",
  "APPLE INC": "AAPL",
  "苹果": "AAPL",
  NVIDIA: "NVDA",
  "NVIDIA CORP": "NVDA",
  "英伟达": "NVDA",
  TESLA: "TSLA",
  "特斯拉": "TSLA",
  MICROSOFT: "MSFT",
  "微软": "MSFT",
  AMAZON: "AMZN",
  "亚马逊": "AMZN",
  ALIBABA: "BABA",
  "阿里巴巴": "BABA",
  TENCENT: "TCEHY",
  "TENCENT HOLDINGS": "TCEHY",
  "TENCENT HOLDINGS ADR": "TCEHY",
  "腾讯": "TCEHY",
};

const TICKER_PATTERN = /^[A-Z][A-Z0-9.-]{0,9}$/;

/** Converts a ticker or a supported company name into the market symbol used by the data APIs. */
export function resolveTickerInput(value: string): string | null {
  const normalized = value.trim().toUpperCase().replace(/\s+/g, " ");
  if (!normalized) return null;
  if (TICKER_PATTERN.test(normalized)) return normalized;
  return COMPANY_TICKERS[normalized] ?? null;
}
