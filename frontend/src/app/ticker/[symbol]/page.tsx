import { Shell } from "@/components/Shell";
import { ForecastFooter, ForecastBadge } from "@/components/ForecastFooter";
import { OptionChainTable } from "@/components/OptionChainTable";
import { PriceChart } from "@/components/PriceChart";
import { TradeCard } from "@/components/TradeCard";
import { SourceBadge, SourceBadgeRow } from "@/components/SourceBadge";
import { api, type Factor, type Signal } from "@/lib/api";
import { fmtNum, signalBg, signalColor } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function TickerPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  const detail = await api.ticker(symbol).catch(() => null);

  if (!detail) {
    return (
      <Shell>
        <h1 className="text-2xl">{symbol.toUpperCase()}</h1>
        <p className="mt-2 text-zinc-500">Unable to load ticker — is the API running?</p>
      </Shell>
    );
  }

  const signal = detail.signal as Signal | null;
  const candles = (detail.candles?.data || []) as Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
  }>;
  const patterns = detail.patterns || {};
  const options = detail.options;
  const contracts = (options?.contracts || []) as Array<{
    symbol: string;
    strike: number;
    expiration: string;
    option_type: string;
    bid?: number | null;
    ask?: number | null;
    volume?: number | null;
    open_interest?: number | null;
    implied_volatility?: number | null;
    delta?: number | null;
  }>;
  const suggestedSymbol = signal?.suggested_contract
    ? String((signal.suggested_contract as { symbol?: string }).symbol || "")
    : null;

  const sourceItems = [
    detail.candles?.source ? { source: detail.candles.source } : null,
    options?.source ? { source: options.source, note: options.note } : null,
    detail.news?.source
      ? { source: detail.news.source, fetchedAt: detail.news.fetched_at, note: detail.news.note }
      : null,
    ...(signal?.sources || []).map((s) => ({ source: s })),
  ].filter(Boolean) as Array<{ source: string; fetchedAt?: string; note?: string }>;

  return (
    <Shell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h1 className="font-display text-3xl tracking-tight">{symbol.toUpperCase()}</h1>
            <ForecastBadge />
          </div>
          <SourceBadgeRow items={sourceItems} />
        </div>
        {signal && (
          <div className={`rounded-lg border px-4 py-2 ${signalBg(signal.action)}`}>
            <span className={`text-lg font-semibold ${signalColor(signal.action)}`}>
              {signal.action}
            </span>
            <span className="ml-3 tabular-nums text-zinc-300">
              {fmtNum(signal.confidence, 0)}% confidence
              {signal.confidence_basis === "heuristic_uncalibrated" && (
                <span className="ml-1 text-xs text-zinc-500">(uncalibrated)</span>
              )}
            </span>
            {signal.risk_reward != null && (
              <span className="ml-3 text-sm text-zinc-400">R/R {fmtNum(signal.risk_reward, 2)}</span>
            )}
          </div>
        )}
      </div>

      <PriceChart
        candles={candles}
        support={patterns.levels?.support}
        resistance={patterns.levels?.resistance}
        entry={signal?.entry}
        stop={signal?.stop_loss}
        targets={signal?.take_profit}
      />

      {(patterns.patterns?.length ?? 0) > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {patterns.patterns!.map((p) => (
            <span
              key={p.name}
              className="rounded border border-zinc-700 bg-zinc-900/50 px-2 py-0.5 text-[11px] text-zinc-400"
            >
              {p.name} · {p.direction}
            </span>
          ))}
        </div>
      )}

      {signal && (
        <div className="mt-6">
          <TradeCard signal={signal} />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Factor breakdown
          </h2>
          <ul className="space-y-2 text-sm">
            {(signal?.factors || []).map((f: Factor) => (
              <li
                key={f.name}
                className="flex items-start justify-between gap-3 border-b border-zinc-800/60 pb-2"
              >
                <div>
                  <div className="text-zinc-200">{f.name}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-zinc-500">{f.observed}</span>
                    <SourceBadge source={f.source} className="scale-95" />
                  </div>
                </div>
                <div
                  className={`tabular-nums ${
                    f.contribution > 0
                      ? "text-emerald-400"
                      : f.contribution < 0
                        ? "text-rose-400"
                        : "text-zinc-500"
                  }`}
                >
                  {f.contribution > 0 ? "+" : ""}
                  {f.contribution.toFixed(2)}
                </div>
              </li>
            ))}
            {(signal?.missing_factors || []).map((m) => (
              <li key={m} className="text-[11px] text-amber-500/80">
                Missing (not coerced to neutral): {m}
              </li>
            ))}
          </ul>
        </section>

        {(signal?.confidence_breakdown?.length ?? 0) > 0 && (
          <section className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4 lg:col-span-2">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Confidence breakdown
            </h2>
            <ul className="grid gap-2 sm:grid-cols-2">
              {signal!.confidence_breakdown!.map((c) => (
                <li
                  key={c.name}
                  className="flex items-center justify-between rounded border border-zinc-800/80 px-3 py-2 text-sm"
                >
                  <span className="text-zinc-300">{c.name}</span>
                  <span className="tabular-nums text-zinc-400">{fmtNum(c.points, 1)} pts</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            AI explanation
          </h2>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-zinc-300">
            {(signal?.reasoning || []).join("\n")}
          </pre>
        </section>
      </div>

      <section className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Option chain
          </h2>
          {options?.source && <SourceBadge source={options.source} note={options.note} />}
        </div>
        <OptionChainTable
          contracts={contracts}
          suggestedSymbol={suggestedSymbol}
          source={options?.source}
        />
      </section>

      <ForecastFooter disclaimer={detail.disclaimer || signal?.disclaimer} />
    </Shell>
  );
}
