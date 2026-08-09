"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, ChevronDown, FileText, Maximize2, Sparkles } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { MarkdownReport } from "@/components/stock/MarkdownReport";
import type { Citation, ScoreResult } from "@/lib/types";

export function ThesisCard({
  score,
  narrative,
  citations,
  onCitationClick,
}: {
  score: ScoreResult;
  narrative: string;
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
}) {
  const [readerOpen, setReaderOpen] = useState(false);
  const rawReport = narrative && narrative !== score.thesis
    ? `${score.thesis}\n\n${narrative}`
    : score.thesis;
  const fullReport = removeRepeatedDataLimitations(rawReport);
  const isLongReport = fullReport.length > 420;

  return (
    <>
      <div className="app-card rounded-xl p-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>Agent 核心研报总结</span>
          </div>
          <button
            type="button"
            onClick={() => setReaderOpen(true)}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:border-primary/20 hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            aria-label="放大查看全文"
            title="放大查看全文"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
        <div className="relative">
          <div
            id="agent-report-body"
            className={`${isLongReport ? "h-32" : "max-h-32"} overflow-hidden`}
          >
            <MarkdownReport content={fullReport} compact className="text-foreground/88" />
          </div>
          {isLongReport && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-card via-card/90 to-transparent" />
          )}
        </div>

        {isLongReport && (
          <button
            type="button"
            onClick={() => setReaderOpen(true)}
            className="mx-auto mt-1 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-secondary/70"
          >
            查看全文 <ChevronDown className="h-3.5 w-3.5" />
          </button>
        )}

        {citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {citations.map((c) => (
              <button
                key={c.concept}
                onClick={() => onCitationClick(c)}
                className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-secondary px-2.5 py-1 text-[11px] text-secondary-foreground transition-colors hover:border-primary"
              >
                <FileText className="h-3 w-3" />[{c.form} · {c.label}]
              </button>
            ))}
          </div>
        )}

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="overflow-hidden rounded-lg border border-[#cfe1d6] bg-[#fbfdfb]">
            <div className="flex items-center gap-2 border-b border-[#dce9e0] bg-[#f1f8f3] px-3 py-2 text-xs font-semibold text-[#168653]">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#168653] text-white"><ArrowUp className="h-3 w-3" /></span>
              核心利好催化剂
            </div>
            <ol className="space-y-2 px-3 py-3 text-[11px] leading-4 text-foreground/85">
              {score.bullPoints.map((point, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#168653] text-[9px] font-semibold text-white">{i + 1}</span>
                  <span>{point}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="overflow-hidden rounded-lg border border-[#ead0cc] bg-[#fffdfd]">
            <div className="flex items-center gap-2 border-b border-[#f0dedb] bg-[#fcf3f1] px-3 py-2 text-xs font-semibold text-[#c7473c]">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#c7473c] text-white"><ArrowDown className="h-3 w-3" /></span>
              下行风险
            </div>
            <ol className="space-y-2 px-3 py-3 text-[11px] leading-4 text-foreground/85">
              {score.bearPoints.map((point, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#c7473c] text-[9px] font-semibold text-white">{i + 1}</span>
                  <span>{point}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      <Dialog open={readerOpen} onOpenChange={setReaderOpen}>
        <DialogContent className="max-h-[min(78vh,720px)] max-w-4xl">
          <div className="border-b border-border/70 px-5 py-4 pr-14">
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Agent 核心研报全文
            </DialogTitle>
          </div>
          <div
            data-slot="dialog-scroll"
            className="report-scroll min-h-0 overflow-y-auto overscroll-contain px-5 py-4"
          >
            <MarkdownReport content={fullReport} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function removeRepeatedDataLimitations(content: string) {
  const blocks = content.replace(/\r\n?/g, "\n").split(/\n\s*\n/);
  let hasDataLimitation = false;

  return blocks
    .filter((block) => {
      const plain = block.replace(/[*_`>#]/g, "").replace(/\s+/g, " ");
      const isDataLimitation = /(api\s*限流|接口限流|数据(?:源|接口)?.{0,18}(?:无法获取|获取失败|受限)|(?:财务指标|财务数据|利润表|新闻情绪).{0,24}(?:无法获取|获取失败)|数据有限|仅成功获取.*股价数据)/i.test(plain);
      if (!isDataLimitation) return true;
      if (hasDataLimitation) return false;
      hasDataLimitation = true;
      return true;
    })
    .join("\n\n");
}
