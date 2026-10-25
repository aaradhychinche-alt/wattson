import type { Metadata } from "next";

import { MobileNav, SidebarNav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "WATTSON - AI cloud optimizer",
  description:
    "Evidence-based MEASURE -> ANALYZE -> SIMULATE -> APPROVE -> EXECUTE -> VERIFY control plane for AI workloads.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col lg:flex-row">
          <aside className="border-b border-slate-800/80 bg-ink-950/70 px-4 py-5 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r lg:px-5 lg:py-7">
            <div className="mb-5 flex items-center justify-between gap-3 lg:mb-8 lg:block">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-sky-500/40 bg-sky-500/10 font-mono text-lg font-bold text-sky-300">
                  W
                </div>
                <div>
                  <p className="text-base font-semibold tracking-[0.18em] text-white">WATTSON</p>
                  <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                    AI cloud optimizer
                  </p>
                </div>
              </div>
              <span className="hidden rounded-full border border-fuchsia-500/40 bg-fuchsia-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-fuchsia-300 lg:inline-flex">
                Provenance first
              </span>
            </div>

            <div className="hidden lg:block">
              <SidebarNav />
              <div className="mt-8 rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Safety contract
                </p>
                <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-400">
                  <li>No paid execution without recorded approval.</li>
                  <li>Every metric carries provenance.</li>
                  <li>Missing data is shown as unavailable.</li>
                  <li>Regressions are reported honestly.</li>
                </ul>
              </div>
            </div>

            <div className="lg:hidden">
              <MobileNav />
            </div>
          </aside>

          <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">{children}</main>
        </div>
      </body>
    </html>
  );
}
