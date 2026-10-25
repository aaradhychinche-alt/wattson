"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Overview", hint: "Loop status" },
  { href: "/workloads", label: "Workloads", hint: "Inputs and constraints" },
  { href: "/optimizations", label: "Optimizations", hint: "Plans and approvals" },
  { href: "/workflows", label: "Workflows", hint: "Temporal execution" },
  { href: "/reports", label: "Reports", hint: "Verified evidence" },
  { href: "/settings", label: "Settings", hint: "Safety and integrations" },
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
            className={`group flex items-center gap-3 rounded-xl border px-3 py-2.5 transition ${
              active
                ? "border-sky-500/40 bg-sky-500/10 text-white"
                : "border-transparent text-slate-400 hover:border-slate-800 hover:bg-slate-900/60 hover:text-slate-200"
            }`}
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-lg border text-[10px] font-bold ${
                active
                  ? "border-sky-400/40 bg-sky-400/10 text-sky-300"
                  : "border-slate-800 bg-slate-900 text-slate-500 group-hover:text-slate-300"
              }`}
            >
              {String(index + 1).padStart(2, "0")}
            </span>
            <span>
              <span className="block text-sm font-medium">{item.label}</span>
              <span className="block text-[11px] text-slate-500">{item.hint}</span>
            </span>
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
            className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium ${
              active
                ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
                : "border-slate-800 bg-slate-900/60 text-slate-400"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
