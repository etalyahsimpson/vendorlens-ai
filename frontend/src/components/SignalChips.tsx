import type { MatchSignals } from "../api/types";

type SignalValue = "same" | "different" | "missing";

function Chip({ label, value }: { label: string; value: SignalValue }) {
  const styles: Record<SignalValue, string> = {
    same: "bg-brand-teal-light text-brand-teal-dark",
    different: "bg-red-50 text-red-700",
    missing: "bg-navy-50 text-navy-400",
  };
  const icons: Record<SignalValue, string> = { same: "✓", different: "✕", missing: "–" };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${styles[value]}`}
      title={`${label}: ${value}`}
    >
      <span aria-hidden="true">{icons[value]}</span>
      {label}
    </span>
  );
}

/** Compact evidence chips rendered inside the match table rows. */
export default function SignalChips({ signals }: { signals: MatchSignals }) {
  return (
    <div className="flex flex-wrap items-center gap-1" aria-label="Matching evidence">
      <span className="inline-flex items-center rounded bg-navy-50 px-1.5 py-0.5 text-[11px] font-semibold text-navy-700">
        Name {Math.round(signals.name_similarity * 100)}%
      </span>
      <Chip label="Website" value={signals.website} />
      <Chip label="City" value={signals.city} />
      <Chip label="Postal" value={signals.postal_code} />
      {signals.legal_suffix === "same" && (
        <span className="inline-flex items-center rounded bg-navy-50 px-1.5 py-0.5 text-[11px] font-semibold text-navy-700">
          Suffix
        </span>
      )}
    </div>
  );
}
