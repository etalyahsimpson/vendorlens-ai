import { useState } from "react";
import type { MatchSuggestionItem, RecordBrief } from "../api/types";
import { DECISION_LABELS } from "./BandBadge";

function Field({
  label,
  left,
  right,
}: {
  label: string;
  left: string | null;
  right: string | null;
}) {
  const same = left !== null && right !== null && left === right;
  return (
    <tr className="border-t border-navy-50">
      <th scope="row" className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-navy-400">
        {label}
      </th>
      <td className={`px-4 py-2.5 text-sm ${same ? "font-medium text-brand-teal-dark" : "text-brand-ink"}`}>
        {left ?? <span className="text-navy-300">— not provided —</span>}
      </td>
      <td className={`px-4 py-2.5 text-sm ${same ? "font-medium text-brand-teal-dark" : "text-brand-ink"}`}>
        {right ?? <span className="text-navy-300">— not provided —</span>}
      </td>
    </tr>
  );
}

interface CompareDrawerProps {
  item: MatchSuggestionItem;
  onDecide: (
    suggestionId: string,
    decision: "confirm_same" | "reject_match" | "needs_investigation",
    notes?: string,
  ) => void;
  deciding: boolean;
}

const DECISION_BUTTONS = [
  {
    value: "confirm_same",
    label: "Confirm same entity",
    className:
      "bg-brand-teal text-white hover:bg-brand-teal-dark focus-visible:ring-brand-teal",
  },
  {
    value: "reject_match",
    label: "Not the same entity",
    className:
      "bg-white text-red-700 border border-red-200 hover:bg-red-50 focus-visible:ring-red-300",
  },
  {
    value: "needs_investigation",
    label: "Needs investigation",
    className:
      "bg-white text-amber-700 border border-amber-300 hover:bg-amber-50 focus-visible:ring-amber-400",
  },
] as const;

export default function CompareDrawer({ item, onDecide, deciding }: CompareDrawerProps) {
  const [notes, setNotes] = useState("");
  const left: RecordBrief = item.left;
  const right: RecordBrief = item.right;

  return (
    <div className="border-t border-navy-100 bg-navy-50/60 px-4 py-5 sm:px-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="card overflow-hidden">
          <div className="grid grid-cols-[130px_1fr_1fr] bg-navy-100/70 text-xs font-bold uppercase tracking-wide text-navy-500">
            <div className="px-4 py-2">Field</div>
            <div className="px-4 py-2">Record A</div>
            <div className="px-4 py-2">Record B</div>
          </div>
          <table className="w-full table-fixed">
            <tbody>
              <Field label="Supplier ID" left={left.supplier_id} right={right.supplier_id} />
              <Field label="Name" left={left.supplier_name} right={right.supplier_name} />
              <Field label="Address" left={left.street_address} right={right.street_address} />
              <Field label="City" left={left.city} right={right.city} />
              <Field label="State" left={left.state} right={right.state} />
              <Field label="Postal code" left={left.postal_code} right={right.postal_code} />
              <Field label="Country" left={left.country} right={right.country} />
              <Field label="Website" left={left.website} right={right.website} />
            </tbody>
          </table>
        </div>

        <div className="card flex flex-col p-4">
          <h4 className="text-sm font-bold text-navy-900">Review decision</h4>
          <p className="mt-1 text-xs text-navy-500">
            Your decision is saved to the database and included in the exported
            report. Nothing is merged automatically.
          </p>
          <div className="mt-3 space-y-2">
            {DECISION_BUTTONS.map((btn) => {
              const active = item.review_decision?.decision === btn.value;
              return (
                <button
                  key={btn.value}
                  disabled={deciding}
                  onClick={() => onDecide(item.suggestion_id, btn.value, notes || undefined)}
                  className={`w-full rounded-md px-3 py-2 text-sm font-semibold shadow-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50 ${btn.className} ${
                    active ? "ring-2 ring-offset-1 ring-navy-800" : ""
                  }`}
                >
                  {active ? "● " : ""}
                  {btn.label}
                </button>
              );
            })}
          </div>
          <label className="mt-3 text-xs font-semibold text-navy-500" htmlFor={`notes-${item.suggestion_id}`}>
            Notes (optional)
          </label>
          <textarea
            id={`notes-${item.suggestion_id}`}
            value={notes}
            maxLength={500}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. same address, different billing system"
            className="mt-1 h-16 w-full resize-none rounded-md border border-navy-200 px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-teal"
          />
          {item.review_decision && (
            <p className="mt-2 text-xs text-navy-500">
              Current: <strong>{DECISION_LABELS[item.review_decision.decision]}</strong>
              {item.review_decision.reviewed_at &&
                ` · ${new Date(item.review_decision.reviewed_at).toLocaleString()}`}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
