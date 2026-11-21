import { useState } from "react";
import type { AnalysisSummary, ModelMetrics } from "../api/types";
import StatCard from "../components/StatCard";
import { InlineSpinner } from "../components/Loading";

interface OverviewProps {
  analysis: AnalysisSummary | null;
  metrics: ModelMetrics | null;
  onExploreSample: () => void;
  onUpload: () => void;
  onReview: () => void;
  onModel: () => void;
  exploring: boolean;
}

const STEPS = [
  {
    title: "Import supplier data",
    body: "Upload a CSV register or open the bundled sample. Files are validated against a documented schema before analysis.",
  },
  {
    title: "Retrieve & score candidates",
    body: "Names are normalized, FAISS similarity search plus deterministic blocking surface candidate pairs, and a trained classifier scores each pair with interpretable evidence.",
  },
  {
    title: "Review with evidence",
    body: "Ranked suggestions show name similarity, website, location and suffix signals. Ambiguous pairs are routed for human review - never merged automatically.",
  },
  {
    title: "Export decisions",
    body: "Download a full findings report with model scores, recommendations, and your review decisions alongside original supplier identifiers.",
  },
];

export default function Overview({
  analysis,
  metrics,
  onExploreSample,
  onUpload,
  onReview,
  onModel,
  exploring,
}: OverviewProps) {
  const [stepOpen, setStepOpen] = useState(0);
  const counts = analysis?.counts;
  const total = counts ? counts.likely + counts.needs_review + counts.unlikely : 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-12">
      {/* Hero */}
      <section className="grid items-start gap-8 lg:grid-cols-[1.25fr_1fr]">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-brand-teal-light px-3 py-1 text-xs font-bold uppercase tracking-wide text-brand-teal-dark ring-1 ring-inset ring-brand-teal/25">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-teal" aria-hidden="true" />
            Procurement data quality
          </div>
          <h1 className="mt-4 text-3xl font-bold leading-tight tracking-tight text-navy-900 sm:text-4xl">
            Find duplicate supplier records, compare the evidence, and review matches
            before they affect procurement data.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-navy-600">
            VendorLens AI analyzes supplier registers imported from different systems,
            surfaces records that may represent the same business, and explains every
            recommendation with concrete matching signals - so your team merges data
            with confidence, not guesswork.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button className="btn-primary" onClick={onExploreSample} disabled={exploring}>
              {exploring ? <InlineSpinner /> : null}
              {exploring ? "Analyzing sample…" : "Explore Sample Data"}
            </button>
            <button className="btn-secondary" onClick={onUpload}>
              Upload Supplier CSV
            </button>
          </div>
          <p className="mt-3 text-xs text-navy-400">
            CSV only · up to 2,000 supplier rows · nothing is sent to third-party
            services
          </p>
        </div>

        {/* Active analysis panel */}
        <div className="card p-5">
          {analysis ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wide text-navy-500">
                  Current analysis
                </h2>
                <span className="rounded bg-navy-50 px-2 py-1 font-mono text-[11px] text-navy-500">
                  {analysis.model_version}
                </span>
              </div>
              <p className="mt-2 truncate text-sm text-navy-600">
                {analysis.source_type === "sample" ? "Sample dataset" : analysis.filename}
                {" · "}
                {new Date(analysis.created_at).toLocaleString()}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <StatCard label="Supplier records" value={analysis.counts.records} />
                <StatCard label="Pairs evaluated" value={analysis.counts.suggestions} />
                <StatCard
                  label="Likely matches"
                  value={analysis.counts.likely}
                  tone="teal"
                  hint="High-confidence duplicates"
                />
                <StatCard
                  label="Needs review"
                  value={analysis.counts.needs_review}
                  tone="amber"
                  hint="Ambiguous - human decision"
                />
              </div>
              {total > 0 && (
                <div className="mt-4">
                  <div className="flex h-2.5 w-full overflow-hidden rounded-full" role="img" aria-label="Recommendation band distribution">
                    <div className="bg-brand-teal" style={{ width: `${(counts!.likely / total) * 100}%` }} />
                    <div className="bg-amber-500" style={{ width: `${(counts!.needs_review / total) * 100}%` }} />
                    <div className="bg-navy-200" style={{ width: `${(counts!.unlikely / total) * 100}%` }} />
                  </div>
                  <div className="mt-1.5 flex justify-between text-[11px] font-semibold text-navy-400">
                    <span>Likely {counts!.likely}</span>
                    <span className="text-amber-600">Review {counts!.needs_review}</span>
                    <span>Unlikely {counts!.unlikely}</span>
                  </div>
                </div>
              )}
              <button className="btn-primary mt-5 w-full" onClick={onReview}>
                Review Matches →
              </button>
            </>
          ) : (
            <>
              <h2 className="text-sm font-bold uppercase tracking-wide text-navy-500">
                Start with sample data
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-navy-600">
                Open a representative supplier register with realistic duplicates,
                lookalike companies, and missing fields - and see computed matching
                suggestions in seconds.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-navy-700">
                {[
                  "Real FAISS candidate retrieval + trained classifier",
                  "Every suggestion shows its matching evidence",
                  "Review decisions persist and export to CSV",
                ].map((line) => (
                  <li key={line} className="flex items-start gap-2">
                    <span className="mt-0.5 font-bold text-brand-teal" aria-hidden="true">✓</span>
                    {line}
                  </li>
                ))}
              </ul>
              <button className="btn-primary mt-5 w-full" onClick={onExploreSample} disabled={exploring}>
                {exploring ? <InlineSpinner /> : null}
                {exploring ? "Analyzing sample…" : "Explore Sample Data"}
              </button>
            </>
          )}
        </div>
      </section>

      {/* How it works */}
      <section className="mt-12" aria-labelledby="how-it-works">
        <h2 id="how-it-works" className="text-lg font-bold text-navy-900">
          How matching works
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <button
              key={step.title}
              onClick={() => setStepOpen(i)}
              className={`card p-4 text-left transition-shadow hover:shadow-card-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal ${
                stepOpen === i ? "ring-2 ring-brand-teal" : ""
              }`}
              aria-pressed={stepOpen === i}
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-navy-900 text-xs font-bold text-white">
                  {i + 1}
                </span>
                <h3 className="text-sm font-bold text-navy-900">{step.title}</h3>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-navy-500">
                {step.body}
              </p>
            </button>
          ))}
        </div>
      </section>

      {/* Model teaser */}
      {metrics && (
        <section className="mt-12" aria-labelledby="model-teaser">
          <div className="card flex flex-col items-start gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 id="model-teaser" className="text-lg font-bold text-navy-900">
                Model performance
              </h2>
              <p className="mt-1 max-w-xl text-sm text-navy-500">
                Measured on the included benchmark dataset with entity-disjoint
                train/test splits.{" "}
                <button
                  className="font-semibold text-brand-teal-dark underline-offset-2 hover:underline"
                  onClick={onModel}
                >
                  See benchmark results and methodology →
                </button>
              </p>
            </div>
            <div className="grid w-full grid-cols-3 gap-3 sm:w-auto">
              <StatCard label="Precision" value={metrics.model.test.precision.toFixed(3)} tone="teal" />
              <StatCard label="Recall" value={metrics.model.test.recall.toFixed(3)} tone="teal" />
              <StatCard label="F1" value={metrics.model.test.f1.toFixed(3)} tone="teal" />
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
