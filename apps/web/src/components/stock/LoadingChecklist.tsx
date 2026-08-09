"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { RunStep } from "@/store/dashboard";

export function LoadingChecklist({ ticker, steps }: { ticker: string; steps: RunStep[] }) {
  return (
    <div className="app-card flex flex-col items-center gap-6 rounded-xl px-10 py-10">
      <div className="relative flex h-16 w-16 items-center justify-center">
        <span className="absolute inset-0 animate-spin rounded-full border-2 border-primary/25 border-t-primary" />
        <span className="h-2.5 w-2.5 rounded-sm bg-primary" />
      </div>
      <div className="text-center">
        <div className="text-base font-semibold">Agent 正在深度解构</div>
        <div className="mt-1 text-sm text-muted-foreground">&ldquo;{ticker}&rdquo;</div>
      </div>

      <div className="w-full max-w-sm space-y-2 rounded-xl border border-border bg-background/60 p-4">
        <AnimatePresence initial={false}>
          {steps.length === 0 && (
            <div className="text-xs text-muted-foreground">正在连接 Agent…</div>
          )}
          {steps.map((step) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2 text-xs"
            >
              {step.status === "pending" && (
                <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
              )}
              {step.status === "done" && (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#6b8f5e]" />
              )}
              {step.status === "error" && (
                <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
              )}
              <span
                className={
                  step.status === "pending" ? "font-medium text-primary" : "text-foreground"
                }
              >
                {step.label}
                {step.caption ? (
                  <span className="block text-[10px] text-muted-foreground">{step.caption}</span>
                ) : null}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
