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
    <div className="inline-flex items-center gap-2 rounded-[6px] border border-[#292d30] bg-[#000000] px-3 py-1.5 font-mono text-xs text-[#a1a4a5]">
      <span
        className={`h-2 w-2 rounded-full transition-colors ${
          active ? "animate-pulse bg-[#70b8ff]" : "bg-[#464a4d]"
        }`}
      />
      <span>{active ? "Live sync (5s)" : "Static state"}</span>
    </div>
  );
}
