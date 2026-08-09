import Link from "next/link";

import { ForecastBadge } from "@/components/ForecastFooter";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/scanner", label: "Scanner" },
  { href: "/news", label: "News" },
  { href: "/insiders", label: "Insiders" },
];

const BANNER_DISCLAIMER =
  "Probabilistic forecasts only — not financial advice. Past patterns do not guarantee future results.";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0b0e11] text-zinc-100">
      <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-[#0b0e11]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="flex shrink-0 items-baseline gap-2">
            <span className="font-display text-xl tracking-tight text-sky-400">OptionEdge</span>
            <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">AI</span>
          </Link>
          <nav
            aria-label="Main navigation"
            className="-mx-1 flex max-w-full items-center gap-1 overflow-x-auto text-sm"
          >
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="shrink-0 rounded px-3 py-1.5 text-zinc-400 transition hover:bg-zinc-800/60 hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2 border-t border-amber-900/40 bg-amber-950/30 px-4 py-1.5 text-center text-[11px] text-amber-200/80">
          <ForecastBadge />
          <span>{BANNER_DISCLAIMER}</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
