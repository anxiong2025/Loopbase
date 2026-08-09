import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

function renderInline(content: string, keyPrefix: string): ReactNode[] {
  const tokenPattern = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*\n]+\*)/g;
  const parts = content.split(tokenPattern).filter(Boolean);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;

    if ((part.startsWith("**") && part.endsWith("**")) || (part.startsWith("__") && part.endsWith("__"))) {
      return <strong key={key} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
    }

    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }

    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key} className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.9em] text-foreground">{part.slice(1, -1)}</code>;
    }

    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const href = /^https?:\/\//i.test(link[2]) ? link[2] : "#";
      return (
        <a
          key={key}
          href={href}
          target={href === "#" ? undefined : "_blank"}
          rel={href === "#" ? undefined : "noreferrer"}
          className="font-medium text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary"
        >
          {link[1]}
        </a>
      );
    }

    return part;
  });
}

function isHorizontalRule(line: string) {
  return /^(?:-{3,}|\*{3,}|_{3,})$/.test(line.trim());
}

export function MarkdownReport({
  content,
  className,
  compact = false,
}: {
  content: string;
  className?: string;
  compact?: boolean;
}) {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const rawLine = lines[index];
    const line = rawLine.trim();

    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push(
        <pre key={`code-${index}`} className="overflow-x-auto rounded-lg bg-[#1d1c19] px-4 py-3 text-xs leading-6 text-white/90">
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = Math.min(heading[1].length, 4);
      const headingClasses = {
        1: "text-xl",
        2: "text-lg",
        3: "text-base",
        4: "text-sm",
      }[level];
      blocks.push(
        <div key={`heading-${index}`} role="heading" aria-level={level} className={cn("font-semibold leading-snug text-foreground", headingClasses)}>
          {renderInline(heading[2], `heading-${index}`)}
        </div>
      );
      index += 1;
      continue;
    }

    if (isHorizontalRule(line)) {
      blocks.push(<hr key={`rule-${index}`} className="border-0 border-t border-border/80" />);
      index += 1;
      continue;
    }

    if (/^[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*+]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*+]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={`list-${index}`} className="list-disc space-y-1.5 pl-5 marker:text-primary">
          {items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item, `list-${index}-${itemIndex}`)}</li>)}
        </ul>
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={`ordered-${index}`} className="list-decimal space-y-1.5 pl-5 marker:font-semibold marker:text-primary">
          {items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item, `ordered-${index}-${itemIndex}`)}</li>)}
        </ol>
      );
      continue;
    }

    if (line.startsWith(">")) {
      const quoteLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(
        <blockquote key={`quote-${index}`} className="rounded-r-lg border-l-2 border-primary bg-secondary/55 px-4 py-2 text-foreground/80">
          {renderInline(quoteLines.join(" "), `quote-${index}`)}
        </blockquote>
      );
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,6})\s+/.test(lines[index].trim()) &&
      !isHorizontalRule(lines[index]) &&
      !/^[-*+]\s+/.test(lines[index].trim()) &&
      !/^\d+\.\s+/.test(lines[index].trim()) &&
      !lines[index].trim().startsWith(">") &&
      !lines[index].trim().startsWith("```")
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push(
      <p key={`paragraph-${index}`}>
        {renderInline(paragraphLines.join(" "), `paragraph-${index}`)}
      </p>
    );
  }

  return (
    <div
      className={cn(
        "space-y-4 text-sm leading-7 text-muted-foreground",
        compact && "space-y-2 text-[13px] leading-6",
        className
      )}
    >
      {blocks}
    </div>
  );
}
