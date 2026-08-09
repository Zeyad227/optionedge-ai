import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(digits)}%`;
}

export function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function signalColor(action: string): string {
  if (action === "Buy") return "text-emerald-400";
  if (action === "Sell") return "text-rose-400";
  return "text-amber-400";
}

export function signalBg(action: string): string {
  if (action === "Buy") return "bg-emerald-500/15 border-emerald-500/40";
  if (action === "Sell") return "bg-rose-500/15 border-rose-500/40";
  return "bg-amber-500/15 border-amber-500/40";
}
