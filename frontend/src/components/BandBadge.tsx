import type { Band } from "../api/types";

const CONFIG: Record<Band, { label: string; className: string; dot: string }> = {
  likely_match: {
    label: "Likely match",
    className: "bg-brand-teal-light text-brand-teal-dark ring-brand-teal/30",
    dot: "bg-brand-teal",
  },
  needs_review: {
    label: "Needs review",
    className: "bg-brand-amber-light text-amber-800 ring-amber-500/30",
    dot: "bg-amber-500",
  },
  unlikely_match: {
    label: "Unlikely match",
    className: "bg-navy-50 text-navy-600 ring-navy-200",
    dot: "bg-navy-300",
  },
};

export default function BandBadge({ band }: { band: Band }) {
  const cfg = CONFIG[band];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ring-1 ring-inset ${cfg.className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} aria-hidden="true" />
      {cfg.label}
    </span>
  );
}

export const DECISION_LABELS: Record<string, string> = {
  confirm_same: "Confirmed same entity",
  reject_match: "Not the same entity",
  needs_investigation: "Needs investigation",
};
