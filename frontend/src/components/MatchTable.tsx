import { Fragment, useState } from "react";
import type { MatchSuggestionItem } from "../api/types";
import BandBadge, { DECISION_LABELS } from "./BandBadge";
import CompareDrawer from "./CompareDrawer";
import SignalChips from "./SignalChips";

export type SortKey = "score" | "name";

interface MatchTableProps {
  items: MatchSuggestionItem[];
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
  onDecide: (
    suggestionId: string,
    decision: "confirm_same" | "reject_match" | "needs_investigation",
    notes?: string,
  ) => void;
  decidingId: string | null;
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const tone =
    score >= 0.85 ? "bg-brand-teal" : score >= 0.5 ? "bg-amber-500" : "bg-navy-300";
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-14 overflow-hidden rounded-full bg-navy-100"
        role="img"
        aria-label={`Match score ${pct}%`}
      >
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-xs font-bold text-navy-800">{pct}%</span>
    </div>
  );
}

function DecisionChip({ decision }: { decision: string }) {
  const styles: Record<string, string> = {
    confirm_same: "bg-brand-teal-light text-brand-teal-dark",
    reject_match: "bg-red-50 text-red-700",
    needs_investigation: "bg-brand-amber-light text-amber-800",
  };
  return (
    <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-semibold ${styles[decision] ?? ""}`}>
      {DECISION_LABELS[decision] ?? decision}
    </span>
  );
}

export default function MatchTable({
  items,
  sortKey,
  onSortChange,
  onDecide,
  decidingId,
}: MatchTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full min-w-[760px] text-left">
          <thead>
            <tr className="border-b border-navy-100 bg-navy-50/70 text-[11px] font-bold uppercase tracking-wide text-navy-500">
              <th scope="col" className="px-4 py-3">
                <button
                  className="inline-flex items-center gap-1 uppercase hover:text-navy-800"
                  onClick={() => onSortChange("score")}
                  aria-sort={sortKey === "score" ? "descending" : "none"}
                >
                  Score {sortKey === "score" ? "▼" : "↕"}
                </button>
              </th>
              <th scope="col" className="px-4 py-3">
                <button
                  className="inline-flex items-center gap-1 uppercase hover:text-navy-800"
                  onClick={() => onSortChange("name")}
                  aria-sort={sortKey === "name" ? "ascending" : "none"}
                >
                  Supplier A {sortKey === "name" ? "▲" : "↕"}
                </button>
              </th>
              <th scope="col" className="px-4 py-3">Supplier B</th>
              <th scope="col" className="px-4 py-3">Evidence</th>
              <th scope="col" className="px-4 py-3">Recommendation</th>
              <th scope="col" className="px-4 py-3">Decision</th>
              <th scope="col" className="px-4 py-3 text-right">Compare</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const expanded = expandedId === item.suggestion_id;
              return (
                <Fragment key={item.suggestion_id}>
                  <tr
                    className={`border-b border-navy-50 transition-colors hover:bg-navy-50/40 ${
                      expanded ? "bg-navy-50/60" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <ScoreBar score={item.score} />
                    </td>
                    <td className="max-w-[280px] px-4 py-3">
                      <div className="truncate text-sm font-semibold text-navy-900" title={item.left.supplier_name}>
                        {item.left.supplier_name}
                      </div>
                      <div className="font-mono text-[11px] text-navy-400">{item.left.supplier_id}</div>
                    </td>
                    <td className="max-w-[280px] px-4 py-3">
                      <div className="truncate text-sm font-semibold text-navy-900" title={item.right.supplier_name}>
                        {item.right.supplier_name}
                      </div>
                      <div className="font-mono text-[11px] text-navy-400">{item.right.supplier_id}</div>
                    </td>
                    <td className="px-4 py-3">
                      <SignalChips signals={item.signals} />
                    </td>
                    <td className="px-4 py-3">
                      <BandBadge band={item.band} />
                    </td>
                    <td className="px-4 py-3">
                      {item.review_decision ? (
                        <DecisionChip decision={item.review_decision.decision} />
                      ) : (
                        <span className="whitespace-nowrap text-xs text-navy-300">Not reviewed</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setExpandedId(expanded ? null : item.suggestion_id)}
                        aria-expanded={expanded}
                        className="rounded-md border border-navy-200 px-2.5 py-1.5 text-xs font-semibold text-navy-700 transition-colors hover:bg-navy-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal"
                      >
                        {expanded ? "Hide" : "Compare"}
                      </button>
                    </td>
                  </tr>
                  {expanded && (
                    <tr>
                      <td colSpan={7} className="p-0">
                        <CompareDrawer
                          item={item}
                          onDecide={onDecide}
                          deciding={decidingId === item.suggestion_id}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
