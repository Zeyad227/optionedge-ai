import { signalBg, signalColor, fmtNum } from "@/lib/utils";

import type { Signal } from "@/lib/api";

import Link from "next/link";

import { SourceBadgeRow } from "@/components/SourceBadge";

export function SignalCard({ signal }: { signal: Signal }) {
  const sources = (signal.sources || []).map((s) => ({ source: s }));
  const uncalibrated = signal.confidence_basis === "heuristic_uncalibrated";

  return (
    <Link
      href={`/ticker/${signal.symbol}`}
      className={`block rounded-lg border p-4 transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 ${signalBg(signal.action)}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold tracking-wide">{signal.symbol}</div>
          <div className={`text-sm font-medium ${signalColor(signal.action)}`}>
            {signal.action} · {signal.trend}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold tabular-nums">{fmtNum(signal.confidence, 0)}</div>
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">
            confidence{uncalibrated ? " · uncalibrated" : ""}
          </div>
        </div>
      </div>
      {signal.risk_reward != null && (
        <div className="mt-3 text-xs text-zinc-400">
          R/R {fmtNum(signal.risk_reward, 2)}
          {signal.entry != null && <> · Entry {fmtNum(signal.entry)}</>}
        </div>
      )}
      <SourceBadgeRow items={sources} className="mt-2" />
    </Link>
  );
}
