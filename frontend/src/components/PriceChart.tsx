"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  type CandlestickData,
  type IChartApi,
  type LineData,
  type Time,
} from "lightweight-charts";
import { ChartLegend } from "@/components/ChartLegend";
import { emaSeries } from "@/lib/indicators";

type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export function PriceChart({
  candles,
  support,
  resistance,
  entry,
  stop,
  targets,
}: {
  candles: Candle[];
  ema9?: number | null;
  ema20?: number | null;
  support?: number[];
  resistance?: number[];
  entry?: number | null;
  stop?: number | null;
  targets?: number[];
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !candles?.length) return;

    const chart: IChartApi = createChart(ref.current, {
      layout: {
        background: { color: "#0f1419" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      width: ref.current.clientWidth,
      height: 420,
      timeScale: { borderColor: "#374151" },
      rightPriceScale: { borderColor: "#374151" },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#f87171",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });

    const times = candles.map((c) => c.timestamp.slice(0, 10) as Time);
    const closes = candles.map((c) => c.close);

    const data: CandlestickData<Time>[] = candles.map((c, i) => ({
      time: times[i],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(data);

    const addEmaLine = (values: (number | null)[], color: string) => {
      const lineData: LineData<Time>[] = [];
      values.forEach((v, i) => {
        if (v != null) lineData.push({ time: times[i], value: v });
      });
      if (!lineData.length) return;
      const line = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      line.setData(lineData);
    };

    addEmaLine(emaSeries(closes, 9), "#38bdf8");
    addEmaLine(emaSeries(closes, 20), "#a78bfa");

    (support || []).slice(0, 2).forEach((lvl, i) => {
      candleSeries.createPriceLine({
        price: lvl,
        color: "#34d39988",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: i === 0 ? "Support" : "",
      });
    });
    (resistance || []).slice(0, 2).forEach((lvl, i) => {
      candleSeries.createPriceLine({
        price: lvl,
        color: "#f8717188",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: i === 0 ? "Resistance" : "",
      });
    });
    if (entry) {
      candleSeries.createPriceLine({
        price: entry,
        color: "#fbbf24",
        lineWidth: 2,
        title: "Entry",
      });
    }
    if (stop) {
      candleSeries.createPriceLine({
        price: stop,
        color: "#fb7185",
        lineWidth: 2,
        title: "Stop",
      });
    }
    (targets || []).forEach((t, i) => {
      candleSeries.createPriceLine({
        price: t,
        color: "#4ade80",
        lineWidth: 1,
        lineStyle: 2,
        title: `TP${i + 1}`,
      });
    });

    chart.timeScale().fitContent();

    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [candles, support, resistance, entry, stop, targets]);

  if (!candles?.length) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/30 text-sm text-zinc-500">
        No candle data available.
      </div>
    );
  }

  return (
    <div>
      <div ref={ref} className="w-full overflow-hidden rounded-lg border border-zinc-800" />
      <ChartLegend />
    </div>
  );
}
