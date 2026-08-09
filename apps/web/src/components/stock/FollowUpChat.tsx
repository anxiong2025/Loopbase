"use client";

import { useState } from "react";
import { Info, Send, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { streamAnalysis } from "@/lib/api";

type Turn = { role: "user" | "assistant"; text: string };

export function FollowUpChat({ ticker }: { ticker: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(question: string) {
    setTurns((t) => [...t, { role: "user", text: question }]);
    setBusy(true);
    let answer = "";
    try {
      for await (const evt of streamAnalysis(`关于 ${ticker}：${question}`, 5)) {
        if (evt.kind === "done") answer = evt.final_answer ?? "（没有给出回答）";
        if (evt.kind === "error") answer = `出错了：${evt.message}`;
      }
    } catch (err) {
      answer = `请求失败：${err instanceof Error ? err.message : String(err)}`;
    }
    setTurns((t) => [...t, { role: "assistant", text: answer }]);
    setBusy(false);
  }

  return (
    <div className="app-card rounded-xl p-2.5">
      <div className="mb-1 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-primary" /> 向 Agent 追问
        </div>
        <Tooltip>
          <TooltipTrigger
            type="button"
            aria-label="查看追问说明"
            className="flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <Info className="h-3.5 w-3.5" />
          </TooltipTrigger>
          <TooltipContent side="top" align="end" className="max-w-sm leading-5">
            已完成对 {ticker} 的研报，可继续追问财报细节、估值假设或竞争格局。
          </TooltipContent>
        </Tooltip>
      </div>
      {(turns.length > 0 || busy) && (
        <div className="report-scroll max-h-16 space-y-1 overflow-y-auto pr-1">
          {turns.map((t, i) => (
            <div
              key={i}
              className={
                t.role === "user"
                  ? "ml-auto max-w-[80%] rounded-xl rounded-br-sm bg-primary px-3 py-1.5 text-xs text-primary-foreground"
                  : "max-w-[92%] rounded-lg bg-muted/70 px-3 py-2 text-[11px] text-foreground/80"
              }
            >
              <span className="whitespace-pre-wrap">{t.text}</span>
            </div>
          ))}
          {busy && <div className="text-xs text-muted-foreground">Agent 正在查询、思考…</div>}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const q = value.trim();
          if (!q || busy) return;
          setValue("");
          ask(q);
        }}
        className="mt-1.5 flex gap-2"
      >
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="继续追问财报、估值或竞争格局…"
          disabled={busy}
          className="h-8 rounded-lg bg-card px-3 text-xs"
        />
        <Button type="submit" disabled={busy || !value.trim()} className="h-8 gap-2 rounded-lg bg-[#1c1b18] px-4 text-white hover:bg-black">
          <span>提问</span><Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
