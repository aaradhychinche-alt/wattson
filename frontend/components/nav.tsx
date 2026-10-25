"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Overview", hint: "Loop status" },
  { href: "/workloads", label: "Workloads", hint: "Inputs & constraints" },
  { href: "/optimizations", label: "Optimizations", hint: "Plans & approvals" },
  { href: "/workflows", label: "Workflows", hint: "Temporal execution" },
  { href: "/reports", label: "Reports", hint: "Verified evidence" },
  { href: "/settings", label: "Settings", hint: "Safety & integrations" },
];

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="space-y-1" aria-label="Main navigation">
      {items.map((item, index) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`group flex items-center gap-3 rounded-[6px] border px-3 py-2.5 transition-all duration-150 ${
              active
                ? "border-[#292d30] bg-[#0b0e14] text-white"
                : "border-transparent text-[#a1a4a5] hover:border-[#292d30] hover:bg-[#0b0e14]/50 hover:text-white"
            }`}
          >
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-[6px] border font-mono text-[10px] ${
                active
                  ? "border-[#9281f7]/50 bg-[#9281f7]/10 text-[#9281f7]"
                  : "border-[#292d30] bg-[#000000] text-[#6e727a] group-hover:border-[#6e727a] group-hover:text-[#a1a4a5]"
              }`}
            >
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1">
              <span className="block text-sm font-medium tracking-tight">{item.label}</span>
              <span className="block font-mono text-[11px] text-[#6e727a]">{item.hint}</span>
            </div>
            {active ? (
              <span className="h-1.5 w-1.5 rounded-full bg-[#9281f7]" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-2 overflow-x-auto pb-1" aria-label="Mobile navigation">
      {items.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`shrink-0 rounded-[6px] border px-3 py-1.5 font-mono text-xs transition-colors ${
              active
                ? "border-[#9281f7]/60 bg-[#0b0e14] text-white"
                : "border-[#292d30] bg-[#000000] text-[#a1a4a5] hover:text-white"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
