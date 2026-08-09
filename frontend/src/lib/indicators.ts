/** Client-side indicator helpers for chart overlays. */

export function emaSeries(closes: number[], period: number): (number | null)[] {
  if (closes.length === 0 || period < 1) return [];
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let prev: number | null = null;

  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      out.push(null);
      continue;
    }
    if (prev == null) {
      prev = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;
    } else {
      prev = closes[i] * k + prev * (1 - k);
    }
    out.push(prev);
  }
  return out;
}
