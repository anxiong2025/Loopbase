import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-1">
      <Sidebar />
      <div className="min-w-0 flex flex-1 flex-col sm:pl-48">
        <TopBar />
        <div className="flex flex-1 flex-col">{children}</div>
        <div aria-hidden="true" className="h-6 shrink-0" />
        <footer className="mx-5 shrink-0 border-t border-border/70 py-1 text-center text-[10px] leading-5 text-muted-foreground">
          本项目仅用于学习与演示 Agent 应用开发；内容由 Agent 基于公开数据自动生成，可能存在延迟或偏差，仅供学习参考，不构成投资建议或决策依据。
        </footer>
      </div>
    </div>
  );
}
