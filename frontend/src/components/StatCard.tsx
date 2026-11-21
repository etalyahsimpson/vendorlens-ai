import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "teal" | "amber" | "navy";
}

const TONES = {
  default: "text-navy-900",
  teal: "text-brand-teal-dark",
  amber: "text-amber-600",
  navy: "text-navy-700",
};

export default function StatCard({ label, value, hint, tone = "default" }: StatCardProps) {
  return (
    <div className="card p-4">
      <div className="text-[11px] font-bold uppercase tracking-wide text-navy-400">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${TONES[tone]}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-navy-400">{hint}</div>}
    </div>
  );
}
