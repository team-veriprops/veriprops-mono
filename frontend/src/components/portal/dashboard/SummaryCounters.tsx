"use client";

interface Props {
  total: number;
  active: number;
  completed: number;
}

export default function SummaryCounters({ total, active, completed }: Props) {
  if (total === 0) return null;

  const counters = [
    { label: "Total", value: total },
    { label: "Active", value: active },
    { label: "Completed", value: completed },
  ];

  return (
    <div className="flex gap-3 mb-6">
      {counters.map(({ label, value }) => (
        <div
          key={label}
          className="flex-1 flex flex-col items-center py-3 px-4 rounded-xl"
          style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 1px 4px rgba(0,13,34,0.04)" }}
        >
          <span className="text-xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
            {value}
          </span>
          <span className="text-xs font-medium mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}
