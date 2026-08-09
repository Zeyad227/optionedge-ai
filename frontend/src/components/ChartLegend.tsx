const ITEMS = [
  { label: "EMA 9", color: "#38bdf8", style: "solid" },
  { label: "EMA 20", color: "#a78bfa", style: "solid" },
  { label: "Support", color: "#34d399", style: "dashed" },
  { label: "Resistance", color: "#f87171", style: "dashed" },
  { label: "Entry", color: "#fbbf24", style: "solid" },
  { label: "Stop", color: "#fb7185", style: "solid" },
  { label: "Target", color: "#4ade80", style: "dashed" },
] as const;

export function ChartLegend() {
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-zinc-500">
      {ITEMS.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4"
            style={{
              backgroundColor: item.color,
              opacity: item.style === "dashed" ? 0.65 : 1,
            }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}
