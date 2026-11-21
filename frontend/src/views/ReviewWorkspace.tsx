import { useCallback, useEffect, useMemo, useState } from "react";
import type { AnalysisSummary, MatchSuggestionItem } from "../api/types";
import { exportUrl, getAnalysis, getMatches, reviewMatch, toRequestError } from "../api/client";
import MatchTable, { type SortKey } from "../components/MatchTable";
import StatCard from "../components/StatCard";
import EmptyState from "../components/EmptyState";
import { TableSkeleton } from "../components/Loading";

interface ReviewWorkspaceProps {
  analysis: AnalysisSummary | null;
  onAnalysisRefreshed: (summary: AnalysisSummary) => void;
  onGoUpload: () => void;
  notify: (message: string, tone: "success" | "error") => void;
}

const BAND_FILTERS = [
  { value: "", label: "All bands" },
  { value: "likely_match", label: "Likely match" },
  { value: "needs_review", label: "Needs review" },
  { value: "unlikely_match", label: "Unlikely match" },
];

const DECISION_FILTERS = [
  { value: "", label: "All decisions" },
  { value: "__undecided__", label: "Not yet reviewed" },
  { value: "confirm_same", label: "Confirmed same" },
  { value: "reject_match", label: "Not the same" },
  { value: "needs_investigation", label: "Needs investigation" },
];

const PAGE_SIZE = 100;

export default function ReviewWorkspace({
  analysis,
  onAnalysisRefreshed,
  onGoUpload,
  notify,
}: ReviewWorkspaceProps) {
  const [items, setItems] = useState<MatchSuggestionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [band, setBand] = useState("");
  const [decision, setDecision] = useState("");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [visible, setVisible] = useState(PAGE_SIZE);

  const analysisId = analysis?.analysis_id ?? null;

  const load = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    setError(null);
    try {
      const decisionParam = decision === "__undecided__" ? undefined : decision || undefined;
      const page = await getMatches(analysisId, {
        band: band || undefined,
        decision: decisionParam,
        q: query || undefined,
        limit: 500,
      });
      // "Not yet reviewed" needs client-side complement (API filters positives).
      let filtered = page.items;
      if (decision === "__undecided__") {
        filtered = filtered.filter((i) => i.review_decision === null);
      }
      setItems(filtered);
      setTotal(decision === "__undecided__" ? filtered.length : page.total);
    } catch (err) {
      setError(toRequestError(err).message);
    } finally {
      setLoading(false);
    }
  }, [analysisId, band, decision, query]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setVisible(PAGE_SIZE);
  }, [band, decision, query, sortKey]);

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      if (sortKey === "score") return b.score - a.score;
      return a.left.supplier_name.localeCompare(b.left.supplier_name);
    });
    return copy;
  }, [items, sortKey]);

  async function handleDecide(
    suggestionId: string,
    value: "confirm_same" | "reject_match" | "needs_investigation",
    notes?: string,
  ) {
    if (!analysisId) return;
    setDecidingId(suggestionId);
    try {
      const updated = await reviewMatch(suggestionId, value, notes);
      setItems((prev) =>
        prev.map((i) => (i.suggestion_id === suggestionId ? { ...i, review_decision: updated.review_decision } : i)),
      );
      notify("Decision saved.", "success");
      // Refresh the summary counts in the background.
      onAnalysisRefreshed(await getAnalysis(analysisId));
    } catch (err) {
      notify(toRequestError(err).message, "error");
    } finally {
      setDecidingId(null);
    }
  }

  if (!analysis) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
        <EmptyState
          title="No active analysis"
          description="Explore the bundled sample dataset or upload a supplier CSV to generate matching suggestions for review."
          action={
            <button className="btn-primary" onClick={onGoUpload}>
              Upload Supplier CSV
            </button>
          }
        />
      </div>
    );
  }

  const counts = analysis.counts;
  const shown = sorted.slice(0, visible);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-navy-900">
            Review Matches
          </h1>
          <p className="mt-1 text-sm text-navy-500">
            {analysis.source_type === "sample" ? "Sample dataset" : analysis.filename} ·{" "}
            {counts.records} records · {counts.suggestions} candidate pairs ·{" "}
            <span className="font-mono text-xs">{analysis.model_version}</span>
          </p>
        </div>
        <a
          href={exportUrl(analysis.analysis_id)}
          className="btn-secondary"
          download
          aria-label="Export findings as CSV"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Export Findings
        </a>
      </div>

      {/* Summary */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Likely matches" value={counts.likely} tone="teal" />
        <StatCard label="Needs review" value={counts.needs_review} tone="amber" />
        <StatCard label="Unlikely" value={counts.unlikely} tone="navy" />
        <StatCard
          label="Decisions made"
          value={counts.reviewed}
          hint={`${counts.confirmed} confirmed · ${counts.rejected} rejected`}
        />
        <StatCard label="Awaiting decision" value={counts.suggestions - counts.reviewed} />
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="band-filter">Filter by recommendation band</label>
        <select
          id="band-filter"
          value={band}
          onChange={(e) => setBand(e.target.value)}
          className="h-9 rounded-md border border-navy-200 bg-white px-2.5 text-sm font-semibold text-navy-700 focus:outline-none focus:ring-2 focus:ring-brand-teal"
        >
          {BAND_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
        <label className="sr-only" htmlFor="decision-filter">Filter by review decision</label>
        <select
          id="decision-filter"
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="h-9 rounded-md border border-navy-200 bg-white px-2.5 text-sm font-semibold text-navy-700 focus:outline-none focus:ring-2 focus:ring-brand-teal"
        >
          {DECISION_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
        <label className="sr-only" htmlFor="search-input">Search supplier names or IDs</label>
        <input
          id="search-input"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or supplier ID…"
          className="h-9 flex-1 min-w-[180px] rounded-md border border-navy-200 bg-white px-3 text-sm text-navy-800 placeholder:text-navy-300 focus:outline-none focus:ring-2 focus:ring-brand-teal"
        />
        <span className="text-xs font-semibold text-navy-400" aria-live="polite">
          {total} pair{total === 1 ? "" : "s"}
        </span>
      </div>

      {/* Table */}
      <div className="mt-4">
        {loading ? (
          <div className="card">
            <TableSkeleton />
          </div>
        ) : error ? (
          <div role="alert" className="card border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-800">
            {error}
          </div>
        ) : shown.length === 0 ? (
          <EmptyState
            title="No pairs match these filters"
            description="Try clearing the band or decision filters, or search for a different supplier."
          />
        ) : (
          <>
            <MatchTable
              items={shown}
              sortKey={sortKey}
              onSortChange={setSortKey}
              onDecide={handleDecide}
              decidingId={decidingId}
            />
            {visible < sorted.length && (
              <div className="mt-4 text-center">
                <button className="btn-secondary" onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                  Show more ({sorted.length - visible} remaining)
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
