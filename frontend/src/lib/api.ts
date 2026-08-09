/** API client for OptionEdge AI backend */

export type SignalAction = "Buy" | "Sell" | "Avoid";

export interface Factor {
  name: string;
  observed: string;
  direction: "bullish" | "bearish" | "neutral";
  weight: number;
  contribution: number;
  source: string;
}

export interface ConfidenceComponent {
  name: string;
  points: number;
}

export interface Signal {
  symbol: string;
  action: SignalAction;
  trend: string;
  confidence: number | null;
  confidence_basis?: "heuristic_uncalibrated" | "backtest_calibrated";
  confidence_breakdown?: ConfidenceComponent[];
  forecast_type: "probabilistic";
  entry?: number | null;
  stop_loss?: number | null;
  take_profit?: number[];
  risk_reward?: number | null;
  probability_of_profit?: number | null;
  probability_of_profit_basis?: "delta_approximation" | "unavailable";
  factors?: Factor[];
  missing_factors?: string[];
  reasoning?: string[];
  disclaimer?: string;
  sources?: string[];
  suggested_contract?: Record<string, unknown> | null;
}

export interface ForecastMeta {
  forecast_type: "probabilistic";
  disclaimer?: string;
}

export interface Sourced<T> extends ForecastMeta {
  value: T;
  source: string;
  fetched_at: string;
  url?: string | null;
  note?: string | null;
}

export interface InsiderCluster {
  symbol: string;
  direction: string;
  insider_count: number;
  transaction_count: number;
  label: string;
  window_days?: number;
}

export interface ScannerResponse extends ForecastMeta {
  universe: string[];
  all: Signal[];
  top_calls: Signal[];
  top_puts: Signal[];
  highest_ai_score: Signal[];
  highest_risk_reward: Signal[];
}

export interface TickerDetail extends ForecastMeta {
  symbol: string;
  quote?: Sourced<Record<string, unknown>> | null;
  candles?: { source?: string | null; data?: unknown[] };
  indicators?: Record<string, number | null>;
  patterns?: {
    levels?: { support?: number[]; resistance?: number[] };
    patterns?: Array<{ name: string; direction: string }>;
  };
  options?: {
    source?: string;
    note?: string;
    summary?: Record<string, unknown>;
    contracts?: Array<Record<string, unknown>>;
  };
  signal?: Signal | null;
  news?: Sourced<unknown[]> | null;
}

function apiBaseUrl(): string {
  const serverUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL;
  if (serverUrl) return serverUrl.replace(/\/$/, "");
  return "http://localhost:8000";
}

const API_URL = apiBaseUrl();

export function getApiBaseUrl(): string {
  return API_URL;
}

export type ApiResult<T> = { data: T | null; error: boolean };

export async function safeGet<T>(fn: () => Promise<T>): Promise<ApiResult<T>> {
  try {
    const data = await fn();
    return { data, error: false };
  } catch {
    return { data: null, error: true };
  }
}

async function get<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  const apiKey = process.env.API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", headers });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () =>
    get<{
      status: string;
      providers: Record<string, boolean>;
      workers_enabled?: boolean;
    }>("/health"),
  scanner: () => get<ScannerResponse>("/api/scanner"),
  signal: (symbol: string) => get<Signal & ForecastMeta>(`/api/signals/${symbol}`),
  ticker: (symbol: string) => get<TickerDetail>(`/api/market/ticker/${symbol}`),
  news: (symbol?: string) =>
    get<Sourced<unknown[]>>(symbol ? `/api/news?symbol=${symbol}` : "/api/news"),
  insiders: () =>
    get<Sourced<unknown[]> & { clusters?: InsiderCluster[] }>("/api/insiders"),
};
