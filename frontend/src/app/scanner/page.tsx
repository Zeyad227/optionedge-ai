import { Shell } from "@/components/Shell";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ForecastFooter } from "@/components/ForecastFooter";
import { SignalCard } from "@/components/SignalCard";
import { SourceBadge } from "@/components/SourceBadge";
import { api, getApiBaseUrl, safeGet } from "@/lib/api";
import { fmtNum, signalColor } from "@/lib/utils";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function ScannerPage() {
  const { data: scanner, error } = await safeGet(() => api.scanner());
  const all = scanner?.all || [];
  const calls = scanner?.top_calls || [];
  const puts = scanner?.top_puts || [];

  return (
    <Shell>
      <h1 className="font-display mb-1 text-3xl tracking-tight">Trade Scanner</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Ranked by AI factor score across {scanner?.universe?.length ?? 0} symbols.
      </p>

      {error && (
        <ErrorBanner title="Scanner unavailable">
          Could not load scanner results from{" "}
          <code className="text-amber-100">{getApiBaseUrl()}</code>.
        </ErrorBanner>
      )}

      <div className="mb-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-500/80">
            Top call opportunities
          </h2>
          <div className="grid gap-3">
            {!error && calls.length === 0 && <Empty />}
            {calls.map((s) => (
              <SignalCard key={s.symbol} signal={s} />
            ))}
          </div>
        </section>
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-rose-500/80">
            Top put opportunities
          </h2>
          <div className="grid gap-3">
            {!error && puts.length === 0 && <Empty />}
            {puts.map((s) => (
              <SignalCard key={s.symbol} signal={s} />
            ))}
          </div>
        </section>
      </div>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Full universe
        </h2>
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full min-w-[720px] text-left text-sm">
            <caption className="sr-only">Scanner results for all symbols</caption>
            <thead className="bg-zinc-900/80 text-[11px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Symbol
                </th>
                <th scope="col" className="px-3 py-2">
                  Action
                </th>
                <th scope="col" className="px-3 py-2">
                  Trend
                </th>
                <th scope="col" className="px-3 py-2">
                  Confidence
                </th>
                <th scope="col" className="px-3 py-2">
                  R/R
                </th>
                <th scope="col" className="px-3 py-2">
                  Sources
                </th>
              </tr>
            </thead>
            <tbody>
              {all.map((s) => (
                <tr key={s.symbol} className="border-t border-zinc-800/80 hover:bg-zinc-900/50">
                  <td className="px-3 py-2 font-medium">
                    <Link href={`/ticker/${s.symbol}`} className="text-sky-400 hover:underline">
                      {s.symbol}
                    </Link>
                  </td>
                  <td className={`px-3 py-2 ${signalColor(s.action)}`}>{s.action}</td>
                  <td className="px-3 py-2">{s.trend}</td>
                  <td className="px-3 py-2 tabular-nums">{fmtNum(s.confidence, 0)}%</td>
                  <td className="px-3 py-2 tabular-nums">
                    {s.risk_reward != null ? fmtNum(s.risk_reward, 2) : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(s.sources || []).slice(0, 3).map((src) => (
                        <SourceBadge key={src} source={src} className="scale-90" />
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <ForecastFooter disclaimer={scanner?.disclaimer} />
    </Shell>
  );
}

function Empty() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-500">
      No results in this bucket.
    </div>
  );
}
