import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-10 flex flex-col gap-6 border-b border-[#292d30] pb-8 md:flex-row md:items-end md:justify-between">
      <div className="max-w-3xl">
        <div className="mb-3 inline-flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#9281f7]" />
          <p className="font-mono text-xs font-medium uppercase tracking-[0.2em] text-[#9281f7]">
            {eyebrow}
          </p>
        </div>
        <h1 className="text-3xl font-normal tracking-tight text-white md:text-5xl md:leading-[1.1]">
          {title}
        </h1>
        <p className="mt-4 text-sm leading-relaxed text-[#a1a4a5] md:text-base">
          {description}
        </p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[16px] border border-[#292d30] bg-[#000000] transition-colors duration-150 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#f0f0f0]">
          {title}
        </h2>
        {hint ? <p className="mt-1 text-xs text-[#a1a4a5]">{hint}</p> : null}
      </div>
      {right}
    </div>
  );
}

export function TerminalHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-between border-b border-[#292d30] px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#292d30]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#292d30]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#292d30]" />
      </div>
      <span className="font-mono text-xs text-[#a1a4a5]">{title}</span>
      <div className="w-10" />
    </div>
  );
}
