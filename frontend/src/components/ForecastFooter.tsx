export const DEFAULT_DISCLAIMER =
  "Probabilistic forecast only. Not financial advice. Markets can invalidate this outlook without warning.";

export function ForecastBadge() {
  return (
    <span className="inline-flex items-center rounded border border-amber-800/50 bg-amber-950/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200/90">
      Probabilistic forecast
    </span>
  );
}

export function ForecastFooter({ disclaimer }: { disclaimer?: string | null }) {
  return (
    <footer className="mt-8 rounded-lg border border-zinc-800/80 bg-zinc-900/30 px-4 py-3 text-[11px] leading-relaxed text-zinc-500">
      <div className="mb-1 flex items-center gap-2">
        <ForecastBadge />
        <span className="text-zinc-600">forecast_type=probabilistic</span>
      </div>
      {disclaimer || DEFAULT_DISCLAIMER}
    </footer>
  );
}
