"use client";

import { ExternalLink, FileText } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import type { Citation } from "@/lib/types";

function fmtValue(citation: Citation) {
  if (citation.unit === "USD/shares") return `$${citation.value.toFixed(2)}`;
  const v = citation.value;
  if (Math.abs(v) >= 1e8) return `$${(v / 1e8).toFixed(2)} 亿`;
  return `$${v.toLocaleString()}`;
}

export function CitationDrawer({
  citation,
  companyName,
  open,
  onOpenChange,
}: {
  citation: Citation | null;
  companyName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md">
        {citation && (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                {citation.label}
              </SheetTitle>
              <SheetDescription>来自 {companyName} 向 SEC 申报的官方文件</SheetDescription>
            </SheetHeader>

            <div className="space-y-4 px-4">
              <div className="rounded-xl border border-border bg-muted/40 p-4">
                <div className="text-xs text-muted-foreground">申报数值（原始 XBRL 事实）</div>
                <div className="mt-1 text-2xl font-bold text-primary">{fmtValue(citation)}</div>
              </div>

              <dl className="space-y-2 text-sm">
                <Row label="财报科目 (US-GAAP)" value={citation.concept} />
                <Row
                  label="报告期"
                  value={
                    citation.fiscalPeriodEnd
                      ? `${citation.fiscalPeriodEnd}（${citation.fiscalYear ?? ""} ${citation.fiscalPeriod ?? ""}）`
                      : "—"
                  }
                />
                <Row label="文件类型" value={citation.form ?? "—"} />
                <Row label="申报日期" value={citation.filed ?? "—"} />
                <Row label="accession no." value={citation.accessionNumber ?? "—"} mono />
              </dl>

              {citation.sourceUrl && (
                <a
                  href={citation.sourceUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="flex items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  在 SEC.gov 查看原始文件 <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
              <p className="text-xs text-muted-foreground">
                数据直接来自 SEC EDGAR 结构化 XBRL 申报事实，非模型生成。
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 pb-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : ""}>{value}</dd>
    </div>
  );
}
