/** Honest trade setup card — only computable metrics, plainly labelled. */

import { fmtNum, fmtPct, signalColor } from "@/lib/utils";
import type { Signal } from "@/lib/api";

type Contract = {
  symbol?: string;
  strike?: number;
  expiration?: string;
  option_type?: string;
  bid?: number | null;
  ask?: number | null;
  delta?: number | null;
};

function contractMid(contract: Contract | null | undefined): number | null {
  if (!contract) return null;
  if (contract.bid != null && contract.ask != null && contract.ask >= contract.bid) {
    return (contract.bid + contract.ask) / 2;
  }
  return null;
}

export function TradeCard({ signal }: { signal: Signal }) {
  const contract = (signal.suggested_contract || null) as Contract | null;
  const entry = contractMid(contract) ?? signal.entry ?? null;
  const target = signal.take_profit?.[0] ?? null;
  const stop = signal.stop_loss ?? null;

  const optionReward =
    entry != null && target != null && entry > 0 ? (target - entry) / entry : null;
  const optionRisk = entry != null && stop != null && entry > 0 ? (entry - stop) / entry : null;
  const optionRr =
    optionRisk != null && optionRisk > 0 && optionReward != null
      ? optionReward / optionRisk
      : signal.risk_reward;

  const pop =
    signal.probability_of_profit != null
      ? signal.probability_of_profit * 100
      : null;
  const popBasis =
    signal.probability_of_profit_basis === "delta_approximation"
      ? "Risk-neutral ITM probability from option delta (not historical win rate)"
      : null;

  const hasTrade = signal.action !== "Avoid" && (entry != null || signal.entry != null);

  if (!hasTrade) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Trade setup
        </h2>
        <p className="text-sm text-zinc-500">
          No directional trade suggested — signal is <span className={signalColor(signal.action)}>{signal.action}</span>.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Trade setup
      </h2>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-zinc-500">Underlying signal</dt>
          <dd className={`font-medium ${signalColor(signal.action)}`}>
            {signal.action} · {signal.trend}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">Confidence</dt>
          <dd className="tabular-nums text-zinc-200">
            {fmtNum(signal.confidence, 0)}%
            {signal.confidence_basis === "heuristic_uncalibrated" && (
              <span className="ml-1 text-xs text-zinc-500">(uncalibrated heuristic)</span>
            )}
          </dd>
        </div>
        {contract?.symbol && (
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">Suggested contract</dt>
            <dd className="font-mono text-xs text-zinc-300">{contract.symbol}</dd>
          </div>
        )}
        <div>
          <dt className="text-zinc-500">Entry (mid)</dt>
          <dd className="tabular-nums text-zinc-200">{entry != null ? `$${fmtNum(entry, 2)}` : "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Stop loss</dt>
          <dd className="tabular-nums text-zinc-200">
            {stop != null ? `$${fmtNum(stop, 2)}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">Take profit (1st target)</dt>
          <dd className="tabular-nums text-zinc-200">
            {target != null ? `$${fmtNum(target, 2)}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">Risk / reward</dt>
          <dd className="tabular-nums text-zinc-200">
            {optionRr != null ? `1 : ${fmtNum(optionRr, 1)}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">Probability of profit (ITM)</dt>
          <dd className="tabular-nums text-zinc-200">
            {pop != null ? fmtPct(pop, 1) : "Unavailable"}
          </dd>
          {popBasis && <dd className="mt-1 text-[11px] text-zinc-500">{popBasis}</dd>}
        </div>
        <div className="sm:col-span-2">
          <dt className="text-zinc-500">Historical win rate</dt>
          <dd className="text-zinc-500">Not available — run a backtest to measure realised accuracy.</dd>
        </div>
      </dl>
    </section>
  );
}
