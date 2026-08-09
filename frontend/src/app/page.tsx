import { Shell } from "@/components/Shell";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ForecastFooter } from "@/components/ForecastFooter";
import { SignalCard } from "@/components/SignalCard";
import { SourceBadge } from "@/components/SourceBadge";
import { api, getApiBaseUrl, safeGet, type Signal } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [scannerRes, newsRes, insidersRes, healthRes] = await Promise.all([
    safeGet(() => api.scanner()),
    safeGet(() => api.news()),
    safeGet(() => api.insiders()),
    safeGet(() => api.health()),
  ]);

  const scanner = scannerRes.data;
  const news = newsRes.data;
  const insiders = insidersRes.data;
  const health = healthRes.data;

  const top = (scanner?.highest_ai_score || []).slice(0, 6);
  const newsItems = ((news?.value || []) as Array<Record<string, unknown>>).slice(0, 6);
  const insiderItems = ((insiders?.value || []) as Array<Record<string, unknown>>).slice(0, 6);
  const clusters = insiders?.clusters || [];
  const providers = health?.providers || {};

  const allFailed = scannerRes.error && newsRes.error && insidersRes.error;
  const scannerOnlyFailed = scannerRes.error && !newsRes.error && !insidersRes.error;

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl tracking-tight text-zinc-50">Market Desk</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Live-sourced signals with cited provenance. Every recommendation is a probabilistic
            forecast.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px]" role="list" aria-label="Provider status">
          {Object.entries(providers).map(([name, ok]) => (
            <span
              key={name}
              role="listitem"
              aria-label={`${name} provider ${ok ? "reachable" : "unavailable"}`}
              className={`rounded border px-2 py-0.5 ${
                ok
                  ? "border-emerald-800 text-emerald-400"
                  : "border-zinc-700 text-zinc-500 line-through"
              }`}
            >
              {name}
            </span>
          ))}
        </div>
      </div>

      {allFailed && (
        <ErrorBanner title="Backend unreachable">
          Could not reach the API at <code className="text-amber-100">{getApiBaseUrl()}</code>.
          Start the FastAPI server, then refresh.
        </ErrorBanner>
      )}

      {scannerOnlyFailed && (
        <ErrorBanner title="Scanner unavailable">
          News and insider data loaded, but the scanner could not be reached. Cached signals may
          be stale.
        </ErrorBanner>
      )}

      {clusters.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-amber-500/80">
            Insider clusters (30d)
          </h2>
          <div className="flex flex-wrap gap-2">
            {clusters.slice(0, 5).map((c) => (
              <span
                key={`${c.symbol}-${c.direction}`}
                className="rounded border border-amber-800/50 bg-amber-950/20 px-3 py-1.5 text-xs text-amber-100/90"
              >
                {c.symbol}: {c.label}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Today&apos;s top opportunities
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {top.length === 0 && !scannerRes.error && (
            <div className="col-span-full rounded-lg border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-500">
              No scored signals yet. Ensure API keys (especially Alpaca) are set and the scanner
              has run.
            </div>
          )}
          {top.map((s: Signal) => (
            <SignalCard key={s.symbol} signal={s} />
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Top news
            </h2>
            {news?.source && (
              <SourceBadge source={news.source} fetchedAt={news.fetched_at} note={news.note} />
            )}
          </div>
          {newsRes.error ? (
            <ErrorBanner title="News feed unavailable">
              Could not load headlines from the API.
            </ErrorBanner>
          ) : (
            <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800 bg-zinc-900/30">
              {newsItems.length === 0 && (
                <li className="p-4 text-sm text-zinc-500">No news loaded.</li>
              )}
              {newsItems.map((n, i) => (
                <li key={i} className="p-3">
                  <a
                    href={String(n.url || "#")}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-zinc-200 hover:text-sky-400"
                  >
                    {String(n.title || "Untitled")}
                  </a>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-zinc-500">
                    <SourceBadge source={String(n.source || news?.source || "news")} className="scale-90" />
                    {n.sentiment != null && (
                      <span
                        className={
                          n.sentiment === "Bullish"
                            ? "text-emerald-400"
                            : n.sentiment === "Bearish"
                              ? "text-rose-400"
                              : ""
                        }
                      >
                        {String(n.sentiment)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Latest Form 4 filings
            </h2>
            {insiders?.source && (
              <SourceBadge
                source={insiders.source}
                fetchedAt={insiders.fetched_at}
                note={insiders.note}
              />
            )}
          </div>
          {insidersRes.error ? (
            <ErrorBanner title="Insider feed unavailable">
              Could not load SEC Form 4 filings from the API.
            </ErrorBanner>
          ) : (
            <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800 bg-zinc-900/30">
              {insiderItems.length === 0 && (
                <li className="p-4 text-sm text-zinc-500">No insider filings loaded.</li>
              )}
              {insiderItems.map((t, i) => (
                <li key={i} className="flex items-center justify-between gap-3 p-3 text-sm">
                  <div>
                    <div className="text-zinc-200">{String(t.company || "")}</div>
                    <div className="text-[11px] text-zinc-500">
                      {String(t.transaction_type || "Form 4")} · {String(t.insider_name || "")}
                    </div>
                  </div>
                  {Boolean(t.form_url) && (
                    <a
                      href={String(t.form_url)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-sky-400"
                    >
                      EDGAR
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <ForecastFooter disclaimer={scanner?.disclaimer} />
    </Shell>
  );
}
