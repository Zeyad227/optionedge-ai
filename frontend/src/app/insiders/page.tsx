import { Shell } from "@/components/Shell";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ForecastFooter } from "@/components/ForecastFooter";
import { SourceBadge } from "@/components/SourceBadge";
import { api, getApiBaseUrl, safeGet } from "@/lib/api";
import { safeExternalUrl } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function InsidersPage() {
  const { data, error } = await safeGet(() => api.insiders());
  const items = (data?.value || []) as Array<Record<string, unknown>>;
  const clusters = data?.clusters || [];

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl tracking-tight">Insider filings</h1>
          <p className="mt-1 text-sm text-zinc-500">SEC Form 4 feed with cluster detection.</p>
        </div>
        {data?.source && (
          <SourceBadge source={data.source} fetchedAt={data.fetched_at} note={data.note} />
        )}
      </div>

      {error && (
        <ErrorBanner title="Insider feed unavailable">
          Could not load Form 4 filings from <code className="text-amber-100">{getApiBaseUrl()}</code>.
        </ErrorBanner>
      )}

      {clusters.length > 0 && (
        <section className="mb-6 rounded-lg border border-amber-800/40 bg-amber-950/20 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-amber-400/90">
            Cluster activity (30d window)
          </h2>
          <ul className="space-y-2 text-sm">
            {clusters.map((c) => (
              <li key={`${c.symbol}-${c.direction}`} className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-zinc-200">{c.symbol}</span>
                <span className={c.direction === "Bullish" ? "text-emerald-400" : "text-rose-400"}>
                  {c.direction}
                </span>
                <span className="text-zinc-500">{c.label}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">Recent insider Form 4 filings</caption>
          <thead className="bg-zinc-900/80 text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              <th scope="col" className="px-3 py-2">
                Company
              </th>
              <th scope="col" className="px-3 py-2">
                Symbol
              </th>
              <th scope="col" className="px-3 py-2">
                Insider
              </th>
              <th scope="col" className="px-3 py-2">
                Type
              </th>
              <th scope="col" className="px-3 py-2">
                Sentiment
              </th>
              <th scope="col" className="px-3 py-2">
                Filing
              </th>
            </tr>
          </thead>
          <tbody>
            {!error && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-zinc-500">
                  No insider filings loaded.
                </td>
              </tr>
            )}
            {items.map((t, i) => (
              <tr key={i} className="border-t border-zinc-800/80 hover:bg-zinc-900/40">
                <td className="px-3 py-2">{String(t.company || "")}</td>
                <td className="px-3 py-2 font-medium text-sky-400/90">{String(t.symbol || "—")}</td>
                <td className="px-3 py-2">{String(t.insider_name || "")}</td>
                <td className="px-3 py-2">{String(t.transaction_type || "")}</td>
                <td className="px-3 py-2">{String(t.sentiment || "")}</td>
                <td className="px-3 py-2">
                  {Boolean(t.form_url) ? (
                    <a
                      href={safeExternalUrl(t.form_url)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400"
                    >
                      EDGAR
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ForecastFooter disclaimer={data?.disclaimer} />
    </Shell>
  );
}
