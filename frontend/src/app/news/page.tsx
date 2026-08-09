import { Shell } from "@/components/Shell";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ForecastFooter } from "@/components/ForecastFooter";
import { SourceBadge } from "@/components/SourceBadge";
import { api, getApiBaseUrl, safeGet } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function NewsPage() {
  const { data: news, error } = await safeGet(() => api.news());
  const items = (news?.value || []) as Array<Record<string, unknown>>;

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl tracking-tight">News</h1>
          <p className="mt-1 text-sm text-zinc-500">FinBERT-classified headlines with impact scores.</p>
        </div>
        {news?.source && (
          <SourceBadge source={news.source} fetchedAt={news.fetched_at} note={news.note} />
        )}
      </div>

      {error && (
        <ErrorBanner title="News feed unavailable">
          Could not load headlines from <code className="text-amber-100">{getApiBaseUrl()}</code>.
        </ErrorBanner>
      )}

      <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800">
        {!error && items.length === 0 && (
          <li className="p-4 text-sm text-zinc-500">No news articles loaded.</li>
        )}
        {items.map((n, i) => (
          <li key={i} className="p-4">
            <a
              href={String(n.url || "#")}
              target="_blank"
              rel="noreferrer"
              className="text-zinc-100 hover:text-sky-400"
            >
              {String(n.title || "")}
            </a>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <SourceBadge source={String(n.source || news?.source || "news")} />
              {n.sentiment != null && (
                <span
                  className={
                    n.sentiment === "Bullish"
                      ? "text-emerald-400"
                      : n.sentiment === "Bearish"
                        ? "text-rose-400"
                        : "text-zinc-500"
                  }
                >
                  {String(n.sentiment)}
                </span>
              )}
              {n.impact != null && <span className="text-zinc-500">impact {String(n.impact)}</span>}
            </div>
          </li>
        ))}
      </ul>

      <ForecastFooter disclaimer={news?.disclaimer} />
    </Shell>
  );
}
