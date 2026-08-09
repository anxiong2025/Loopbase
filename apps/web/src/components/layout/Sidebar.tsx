"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Star, Scale, History, ChevronDown, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
  disabled?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: "智能研报",
    href: "/stock/NVDA",
    icon: FileText,
    match: (p) => p.startsWith("/stock"),
  },
  {
    label: "对比分析",
    href: "/compare",
    icon: Scale,
    match: (p) => p.startsWith("/compare"),
  },
  {
    label: "自选标的",
    href: "#",
    icon: Star,
    match: () => false,
    disabled: true,
  },
  {
    label: "历史查询",
    href: "#",
    icon: History,
    match: () => false,
    disabled: true,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-48 shrink-0 flex-col border-r border-sidebar-border bg-sidebar/95 px-3 py-6 backdrop-blur-xl sm:flex">
      <Link href="/" className="mb-11 block">
        <div className="flex items-center gap-2">
          <Image
            src="/loopbase-icon.svg"
            alt=""
            width={40}
            height={40}
            priority
            className="h-9 w-9 shrink-0"
          />
          <span className="font-serif text-[20px] leading-none tracking-[0.08em] text-foreground">LOOPBASE</span>
        </div>
        <div className="mt-1.5 inline-flex items-center gap-1 rounded bg-gradient-to-r from-[#9c6500] to-[#d4a331] px-2 py-0.5 text-[10px] font-semibold tracking-[0.2em] text-white shadow-sm">
          <Sparkles className="h-2.5 w-2.5" /> AGENT
        </div>
      </Link>

      <nav className="flex flex-col gap-3">
        {NAV_ITEMS.map((item) => {
          const active = item.match(pathname);
          const Icon = item.icon;
          if (item.disabled) {
            return (
              <div
                key={item.label}
                className="flex cursor-not-allowed items-center justify-between rounded-xl px-3 py-3 text-sm text-muted-foreground/55"
              >
                <span className="flex items-center gap-3">
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.6} />
                  {item.label}
                </span>
              </div>
            );
          }
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`relative flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition-colors ${
                active
                  ? "bg-secondary/75 font-semibold text-secondary-foreground before:absolute before:-left-3 before:h-8 before:w-[3px] before:rounded-r-full before:bg-primary"
                  : "text-foreground/78 hover:bg-muted"
              }`}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.7} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <button className="mt-auto flex items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-muted">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#1d1c19] text-xs font-semibold text-white shadow-sm">
          INV
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">Investor</span>
          <span className="block truncate text-[10px] text-muted-foreground">个人工作区</span>
        </span>
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </button>
    </aside>
  );
}
