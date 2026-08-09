import { fmtNum } from "@/lib/utils";

type Contract = {
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
};

const DISPLAY_LIMIT = 40;

export function OptionChainTable({
  contracts,
  suggestedSymbol,
  source,
}: {
  contracts: Contract[];
  suggestedSymbol?: string | null;
  source?: string | null;
}) {
  if (!contracts.length) {
    return (
      <p className="text-sm text-zinc-500">
        No option chain loaded{source ? ` (${source})` : ""}.
      </p>
    );
  }

  const sorted = [...contracts].sort((a, b) => a.strike - b.strike);
  const rows = sorted.slice(0, DISPLAY_LIMIT);
  const truncated = sorted.length > DISPLAY_LIMIT;

  return (
    <div>
      {truncated && (
        <p className="mb-2 text-xs text-zinc-500">
          Showing {DISPLAY_LIMIT} of {sorted.length} contracts (nearest strikes).
        </p>
      )}
      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Option chain contracts</caption>
          <thead className="bg-zinc-900/80 text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              <th scope="col" className="px-3 py-2">
                Contract
              </th>
              <th scope="col" className="px-3 py-2">
                Type
              </th>
              <th scope="col" className="px-3 py-2">
                Strike
              </th>
              <th scope="col" className="px-3 py-2">
                Exp
              </th>
              <th scope="col" className="px-3 py-2">
                Bid/Ask
              </th>
              <th scope="col" className="px-3 py-2">
                IV
              </th>
              <th scope="col" className="px-3 py-2">
                Δ
              </th>
              <th scope="col" className="px-3 py-2">
                Vol/OI
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const highlighted = suggestedSymbol && c.symbol === suggestedSymbol;
              return (
                <tr
                  key={c.symbol}
                  className={`border-t border-zinc-800/80 ${
                    highlighted
                      ? "bg-sky-950/40 ring-1 ring-inset ring-sky-700/50"
                      : "hover:bg-zinc-900/40"
                  }`}
                >
                  <td className="px-3 py-2 font-mono text-xs text-zinc-300">
                    {c.symbol}
                    {highlighted && (
                      <span className="ml-2 text-[10px] uppercase text-sky-400">Suggested</span>
                    )}
                  </td>
                  <td className="px-3 py-2 capitalize">{c.option_type}</td>
                  <td className="px-3 py-2 tabular-nums">{fmtNum(c.strike)}</td>
                  <td className="px-3 py-2 text-xs text-zinc-400">{c.expiration}</td>
                  <td className="px-3 py-2 tabular-nums text-xs">
                    {fmtNum(c.bid, 2)}/{fmtNum(c.ask, 2)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-xs">
                    {c.implied_volatility != null ? fmtNum(c.implied_volatility * 100, 1) + "%" : "—"}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-xs">{fmtNum(c.delta, 3)}</td>
                  <td className="px-3 py-2 tabular-nums text-xs text-zinc-500">
                    {c.volume ?? "—"}/{c.open_interest ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
