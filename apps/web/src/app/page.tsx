"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { resolveTickerInput } from "@/lib/ticker";

const EXAMPLES = ["NVDA", "TSLA", "AAPL"];

export default function Home() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [inputError, setInputError] = useState("");

  function go(input: string) {
    const ticker = resolveTickerInput(input);
    if (!ticker) {
      setInputError("请输入股票代码或常见公司名，例如 NVDA、腾讯。");
      return;
    }
    setInputError("");
    router.push(`/stock/${encodeURIComponent(ticker)}`);
  }

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center px-6 text-center">
      <Link href="/" aria-label="LOOPBASE 首页" className="absolute left-6 top-7 sm:left-10 sm:top-9">
        <span className="flex items-center gap-2">
          <Image
            src="/loopbase-icon.svg"
            alt=""
            width={40}
            height={40}
            priority
            className="h-8 w-8 shrink-0 sm:h-10 sm:w-10"
          />
          <span className="font-serif text-xl leading-none tracking-[0.1em] text-foreground sm:text-2xl">LOOPBASE</span>
        </span>
      </Link>

      <section className="flex min-h-[calc(100vh+8rem)] w-full -translate-y-12 flex-col items-center justify-center sm:-translate-y-16">
        <h1 className="max-w-2xl text-4xl font-bold leading-tight sm:text-5xl">
          输入股票代码，生成可溯源的 Agent 研报
        </h1>
        <p className="mt-5 max-w-xl text-muted-foreground">
          实时行情与基本面来自 Alpha Vantage，关键财务科目可点击追溯到 SEC 官方申报文件原文。
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            go(value);
          }}
          className="mt-8 flex w-full max-w-lg items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm transition-[border-color,box-shadow] duration-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20"
        >
          <Search className="ml-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <Input
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (inputError) setInputError("");
            }}
            aria-invalid={Boolean(inputError)}
            placeholder="输入股票代码或公司名（如 NVDA、腾讯）"
            className="border-none shadow-none focus-visible:ring-0"
          />
          <Button type="submit" className="shrink-0 gap-1.5">
            生成研报 <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
        {inputError && <p className="mt-2 text-sm text-destructive">{inputError}</p>}

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-sm">
          <span className="text-muted-foreground">热门标的：</span>
          {EXAMPLES.map((t) => (
            <button
              key={t}
              onClick={() => go(t)}
              className="rounded-full border border-border bg-card px-3 py-1 text-primary transition-colors hover:border-primary"
            >
              {t}
            </button>
          ))}
        </div>

      </section>

      <footer className="max-w-xl pb-8 text-center text-xs leading-5 text-muted-foreground">
        本项目仅用于学习与演示 Agent 应用开发。内容基于公开数据自动生成，可能存在延迟或偏差，不构成投资建议或决策依据。
      </footer>
    </main>
  );
}
