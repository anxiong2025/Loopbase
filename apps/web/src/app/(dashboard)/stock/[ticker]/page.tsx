"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { LoadingChecklist } from "@/components/stock/LoadingChecklist";
import { StockHeaderCard } from "@/components/stock/StockHeaderCard";
import { FollowUpChat } from "@/components/stock/FollowUpChat";
import { CitationDrawer } from "@/components/stock/CitationDrawer";
import { InvestmentSidebar } from "@/components/stock/InvestmentSidebar";
import { ResearchWorkspace } from "@/components/stock/ResearchWorkspace";
import { fetchCitations, fetchOverview, streamAnalysis } from "@/lib/api";
import { buildScorePrompt, parseScoreResult, stripScoreJson } from "@/lib/score-prompt";
import { useDashboardStore } from "@/store/dashboard";
import { resolveTickerInput } from "@/lib/ticker";
import type { Citation } from "@/lib/types";

export default function StockPage() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const rawTicker = decodeURIComponent(params.ticker ?? "");
  const resolvedTicker = resolveTickerInput(rawTicker);
  const ticker = resolvedTicker ?? rawTicker.trim().toUpperCase();

  const {
    overview,
    overviewError,
    citations,
    score,
    scoreNarrative,
    scoreError,
    scoreLoading,
    scoreSteps,
    scoreGeneratedAt,
    scoreCacheHit,
    setOverview,
    setOverviewLoading,
    setCitations,
    setCitationsLoading,
    setScoreLoading,
    setScoreResult,
    resetScoreSteps,
    applyScoreEvent,
  } = useDashboardStore();

  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const reportSectionRef = useRef<HTMLDivElement>(null);
  const revealReportOnCompleteRef = useRef(false);

  async function runScore(signal: AbortSignal, forceRefresh: boolean) {
    revealReportOnCompleteRef.current = true;
    resetScoreSteps();
    setScoreLoading(true);
    try {
      let finalAnswer: string | null = null;
      let generatedAt: string | undefined;
      let cacheHit = false;
      for await (const evt of streamAnalysis(buildScorePrompt(ticker), 6, signal, forceRefresh)) {
        applyScoreEvent(evt);
        if (evt.kind === "done") {
          finalAnswer = evt.final_answer;
          generatedAt = evt.generated_at;
          cacheHit = evt.cache_hit ?? false;
        }
        if (evt.kind === "error") throw new Error(evt.message);
      }
      const parsed = parseScoreResult(finalAnswer);
      if (!parsed) {
        setScoreResult(
          null,
          finalAnswer ?? "",
          "Agent 未能给出结构化评分，以下展示原始回答。",
        );
      } else {
        setScoreResult(parsed, stripScoreJson(finalAnswer), null, { generatedAt, cacheHit });
      }
    } catch (err) {
      if (signal.aborted) return; // 组件卸载/换股触发的取消，不是真错误
      setScoreResult(null, "", err instanceof Error ? err.message : "评分生成失败");
    } finally {
      if (!signal.aborted) setScoreLoading(false);
    }
  }

  useEffect(() => {
    if (!resolvedTicker) return;

    setOverviewLoading(true);
    fetchOverview(ticker)
      .then((data) => setOverview(data, null))
      .catch((err) => setOverview(null, err instanceof Error ? err.message : "加载失败"))
      .finally(() => setOverviewLoading(false));

    setCitationsLoading(true);
    fetchCitations(ticker)
      .then((data) => setCitations(data.citations, null))
      .catch((err) => setCitations(null, err instanceof Error ? err.message : "加载失败"))
      .finally(() => setCitationsLoading(false));

    const controller = new AbortController();
    runScore(controller.signal, false);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedTicker, ticker]);

  useEffect(() => {
    if (!resolvedTicker || rawTicker === resolvedTicker) return;
    router.replace(`/stock/${encodeURIComponent(resolvedTicker)}`);
  }, [rawTicker, resolvedTicker, router]);

  useEffect(() => {
    if (scoreLoading || !score || !overview || !revealReportOnCompleteRef.current) return;

    revealReportOnCompleteRef.current = false;
    const frame = requestAnimationFrame(() => {
      if (window.innerWidth >= 1280 && window.innerHeight >= 760) {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        reportSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [overview, score, scoreLoading]);

  const showLoadingChecklist = Boolean(resolvedTicker) && scoreLoading && !score && !scoreError;

  return (
    <>
      <main className="mx-auto w-full max-w-[1440px] flex-1 space-y-2.5 px-4 py-2.5 lg:px-6">
        {!resolvedTicker ? (
          <section className="mx-auto flex max-w-lg flex-col items-center rounded-2xl border border-border bg-card px-6 py-12 text-center shadow-sm">
            <h1 className="text-lg font-semibold">未识别到可用的股票代码</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              请使用股票代码，或输入已支持的公司名。例如：NVDA、AAPL、腾讯。
            </p>
            <Link href="/" className="mt-5 text-sm font-medium text-primary hover:underline">
              返回首页重新搜索
            </Link>
          </section>
        ) : showLoadingChecklist ? (
          <div className="flex justify-center py-16">
            <LoadingChecklist ticker={ticker} steps={scoreSteps} />
          </div>
        ) : (
          <>
            {overviewError && !overview && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                行情/基本面加载失败：{overviewError}
              </div>
            )}

            {overview && (
              <StockHeaderCard
                overview={overview}
                score={score}
                reportMeta={
                  score ? (
                    <div className="mt-0.5 flex items-center justify-end gap-1.5 text-[9px]">
                      <span>
                        {scoreGeneratedAt
                          ? `生成于 ${new Date(scoreGeneratedAt).toLocaleString("zh-CN", {
                              hour: "2-digit",
                              minute: "2-digit",
                              month: "2-digit",
                              day: "2-digit",
                            })}`
                          : "生成于刚刚"}
                        {scoreCacheHit ? " · 缓存" : " · 实时"}
                      </span>
                      <button
                        type="button"
                        disabled={scoreLoading}
                        onClick={() => {
                          const controller = new AbortController();
                          runScore(controller.signal, true);
                        }}
                        className="flex items-center gap-0.5 text-primary transition-opacity hover:opacity-70 disabled:opacity-40"
                      >
                        <RefreshCw className={`h-2.5 w-2.5 ${scoreLoading ? "animate-spin" : ""}`} />
                        重新生成
                      </button>
                    </div>
                  ) : undefined
                }
              />
            )}

            {scoreError && (
              <div className="space-y-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                <div>{scoreError}</div>
                {scoreNarrative && (
                  <p className="whitespace-pre-wrap text-foreground/80">{scoreNarrative}</p>
                )}
              </div>
            )}

            {score && overview && (
              <div
                ref={reportSectionRef}
                className="scroll-mt-20 grid items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_360px]"
              >
                <div className="min-w-0 space-y-2">
                  <ResearchWorkspace
                    ticker={ticker}
                    overview={overview}
                    score={score}
                    narrative={scoreNarrative}
                    citations={citations ?? []}
                    onCitationClick={(citation) => {
                      setSelectedCitation(citation);
                      setDrawerOpen(true);
                    }}
                  />
                  <FollowUpChat key={`chat-${ticker}`} ticker={ticker} />
                </div>
                <div className="min-w-0 xl:flex xl:min-h-0 xl:flex-col xl:pt-10">
                  <InvestmentSidebar overview={overview} score={score} />
                </div>
              </div>
            )}

            {(!score || !overview) && <FollowUpChat key={`chat-${ticker}`} ticker={ticker} />}
          </>
        )}
      </main>

      <CitationDrawer
        citation={selectedCitation}
        companyName={overview?.name ?? ticker}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </>
  );
}
