import type { Metadata } from "next";

import { MobileNav, SidebarNav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "WATTSON — Evidence-Based AI Cloud Optimizer",
  description:
    "Evidence-based MEASURE -> ANALYZE -> SIMULATE -> APPROVE -> EXECUTE -> VERIFY control plane for AI workloads.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark bg-[#000000]">
      <body className="bg-[#000000] text-[#f0f0f0] selection:bg-[#9281f7]/25 selection:text-white">
        <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col lg:flex-row">
          <aside className="border-b border-[#292d30] bg-[#000000] px-4 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r lg:px-6 lg:py-8 flex flex-col justify-between">
            <div>
              {/* Header / Brand */}
              <div className="mb-6 flex items-center justify-between gap-3 lg:mb-8">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-[6px] border border-[#292d30] bg-[#0b0e14] font-mono text-sm font-semibold text-white">
                    <span className="text-[#9281f7]">W</span>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-semibold tracking-[0.14em] text-white">WATTSON</p>
                      <span className="h-1.5 w-1.5 rounded-full bg-[#9281f7]" />
                    </div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#a1a4a5]">
                      AI Cloud Optimizer
                    </p>
                  </div>
                </div>
              </div>

              {/* Announcement Pill */}
              <div className="mb-6 hidden lg:block">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#292d30] bg-[#000000] px-3 py-1 font-mono text-[11px] text-[#f0f0f0]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#3ad389]" />
                  <span>Closed Loop Active</span>
                  <span className="text-[#9281f7]">&gt;</span>
                </div>
              </div>

              {/* Desktop Nav */}
              <div className="hidden lg:block">
                <SidebarNav />
              </div>

              {/* Mobile Nav */}
              <div className="lg:hidden">
                <MobileNav />
              </div>
            </div>

            {/* Bottom Safety Contract */}
            <div className="hidden lg:block pt-6">
              <div className="rounded-[16px] border border-[#292d30] bg-[#000000] p-4">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#9281f7]" />
                  <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-[#a1a4a5]">
                    Safety Contract
                  </p>
                </div>
                <ul className="mt-3 space-y-1.5 font-mono text-[11px] leading-relaxed text-[#6e727a]">
                  <li className="flex items-start gap-1.5">
                    <span className="text-[#a1a4a5]">-</span> No spend without approval
                  </li>
                  <li className="flex items-start gap-1.5">
                    <span className="text-[#a1a4a5]">-</span> Full metric provenance
                  </li>
                  <li className="flex items-start gap-1.5">
                    <span className="text-[#a1a4a5]">-</span> Missing data shown unavailable
                  </li>
                  <li className="flex items-start gap-1.5">
                    <span className="text-[#a1a4a5]">-</span> Regressions reported honestly
                  </li>
                </ul>
              </div>
            </div>
          </aside>

          <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 lg:px-12 lg:py-10 bg-[#000000]">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
