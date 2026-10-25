"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function AutoRefresh({ active }: { active: boolean }) {
  const router = useRouter();

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(timer);
  }, [active, router]);

  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-500">
      <span
        className={`h-1.5 w-1.5 rounded-full ${active ? "animate-pulse bg-sky-400" : "bg-slate-600"}`}
      />
      {active ? "Live refresh every 5s" : "No active workflows"}
    </span>
  );
}
