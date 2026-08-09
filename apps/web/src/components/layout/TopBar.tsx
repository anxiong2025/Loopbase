"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { resolveTickerInput } from "@/lib/ticker";

export function TopBar() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [inputError, setInputError] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const ticker = resolveTickerInput(value);
    if (!ticker) {
      setInputError("请输入股票代码或常见公司名，例如 NVDA、腾讯。");
      return;
    }
    setInputError("");
    setValue("");
    router.push(`/stock/${encodeURIComponent(ticker)}`);
  }

  return (
    <header className="sticky top-0 z-30 border-b border-border/75 bg-background/88 backdrop-blur-xl">
      <div className="flex h-14 items-center gap-3 px-4 lg:gap-4 lg:px-6">
        <Link href="/" className="mr-1 font-serif text-sm tracking-[0.08em] sm:hidden">
          LOOPBASE
        </Link>
        <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-3">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-muted-foreground" />
            <Input
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                if (inputError) setInputError("");
              }}
              aria-invalid={Boolean(inputError)}
              placeholder="输入股票代码或公司名…"
              className="h-9 rounded-xl border-black/10 bg-card pl-11 text-[12px] shadow-[0_1px_2px_rgba(0,0,0,0.02)] focus-visible:border-primary/50 aria-[invalid=true]:border-destructive/60"
            />
            {inputError && (
              <p role="alert" className="absolute left-1 top-full mt-1 text-xs text-destructive">
                {inputError}
              </p>
            )}
          </div>
          <Button type="submit" className="h-9 shrink-0 gap-2 rounded-xl bg-[#1c1b18] px-5 text-white shadow-sm hover:bg-black">
            <Sparkles className="h-4 w-4" />
            <span className="hidden md:inline">生成研报</span>
          </Button>
        </form>
      </div>
    </header>
  );
}
