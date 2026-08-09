import { cn } from "@/lib/utils";

const SOURCE_COLORS: Record<string, string> = {
  alpaca: "border-sky-800/60 bg-sky-950/40 text-sky-300",
  yfinance: "border-violet-800/60 bg-violet-950/40 text-violet-300",
  "sec-edgar": "border-amber-800/60 bg-amber-950/40 text-amber-300",
  finnhub: "border-emerald-800/60 bg-emerald-950/40 text-emerald-300",
  "iv-history": "border-cyan-800/60 bg-cyan-950/40 text-cyan-300",
  fixture: "border-zinc-700 bg-zinc-900/60 text-zinc-400",
};

function badgeClass(source: string): string {
  const key = source.toLowerCase().replace(/\s+/g, "-");
  return SOURCE_COLORS[key] ?? "border-zinc-700 bg-zinc-900/60 text-zinc-400";
}

function fmtFetchedAt(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
}

export function SourceBadge({
  source,
  fetchedAt,
  note,
  className,
}: {
  source: string;
  fetchedAt?: string | null;
  note?: string | null;
  className?: string;
}) {
  const when = fmtFetchedAt(fetchedAt);
  return (
    <span
      className={cn(
        "inline-flex max-w-full flex-wrap items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-medium tracking-wide",
        badgeClass(source),
        className,
      )}
      title={note || undefined}
    >
      <span>{source}</span>
      {when && <span className="opacity-70">· {when}</span>}
    </span>
  );
}

export function SourceBadgeRow({
  items,
  className,
}: {
  items: Array<{ source: string; fetchedAt?: string | null; note?: string | null }>;
  className?: string;
}) {
  const unique = items.filter(
    (item, i, arr) => arr.findIndex((x) => x.source === item.source) === i,
  );
  if (!unique.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {unique.map((item) => (
        <SourceBadge
          key={item.source}
          source={item.source}
          fetchedAt={item.fetchedAt}
          note={item.note}
        />
      ))}
    </div>
  );
}
