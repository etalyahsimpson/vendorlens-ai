import { useEffect, useState } from "react";
import type { ModelMetrics } from "../api/types";
import { getModelMetrics, toRequestError } from "../api/client";
import StatCard from "../components/StatCard";
import { CardSkeleton } from "../components/Loading";
import EmptyState from "../components/EmptyState";

const GITHUB_BASE =
  "https://github.com/etalyahsimpson/vendorlens-ai/blob/main";

const FEATURE_EXPLANATIONS: Record<string, string> = {
  name_char_similarity: "Character-level similarity of normalized supplier names",
  name_token_jaccard: "Shared-word overlap between the two names",
  name_token_containment: "How much of the smaller name's vocabulary appears in the larger",
  suffix_both_present_same: "Both legal suffixes present and identical (e.g. both LLC)",
  suffix_both_present_different: "Both legal suffixes present but different",
  city_both_present_equal: "Both cities present and equal",
  city_both_present_different: "Both cities present but different",
  city_missing: "At least one record has no city on file",
  state_both_present_equal: "Both states present and equal",
  state_both_present_different: "Both states present but different",
  state_missing: "At least one record has no state on file",
  postal_both_present_equal: "Both postal codes present and equal",
  postal_both_present_different: "Both postal codes present but different",
  postal_missing: "At least one record has no postal code on file",
  website_both_present_equal: "Both website domains present and identical",
  website_both_present_different: "Both website domains present but different",
  website_missing: "At least one record has no website on file",
  address_char_similarity: "Character similarity of normalized street addresses",
  address_missing: "At least one record has no address on file",
};

export default function ModelEvidence() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getModelMetrics()
      .then(setMetrics)
      .catch((err) => setError(toRequestError(err).message));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
        <EmptyState
          title="Model metrics unavailable"
          description={error}
        />
      </div>
    );
  }
  if (!metrics) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-4 py-8 sm:px-6">
        <CardSkeleton lines={4} />
        <CardSkeleton lines={6} />
      </div>
    );
  }

  const test = metrics.model.test;
  const base = metrics.baseline.test;
  const cm = test.confusion_matrix;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      <h1 className="text-2xl font-bold tracking-tight text-navy-900">
        Model Performance
      </h1>
      <p className="mt-2 max-w-3xl text-sm text-navy-600">
        Benchmark results for the trained matching model. Metrics are measured on the
        included benchmark dataset using entity-disjoint train/test splits —{" "}
        <a
          className="font-semibold text-brand-teal-dark underline-offset-2 hover:underline"
          href={`${GITHUB_BASE}/docs/ML_METHODOLOGY.md`}
          target="_blank"
          rel="noopener noreferrer"
        >
          read the methodology
        </a>{" "}
        for dataset provenance, thresholds and limitations.
      </p>

      {/* Key metrics */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Precision" value={test.precision.toFixed(3)} tone="teal" hint="Held-out test split" />
        <StatCard label="Recall" value={test.recall.toFixed(3)} tone="teal" hint="Held-out test split" />
        <StatCard label="F1 score" value={test.f1.toFixed(3)} tone="teal" hint="Held-out test split" />
        <StatCard
          label="Candidate recall"
          value={metrics.candidate_generation.candidate_recall.test.toFixed(3)}
          hint="Pairs surfaced by retrieval"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Confusion matrix */}
        <section className="card p-5" aria-labelledby="cm-heading">
          <h2 id="cm-heading" className="text-sm font-bold uppercase tracking-wide text-navy-500">
            Confusion matrix · trained model
          </h2>
          <div className="mx-auto mt-4 grid max-w-sm grid-cols-2 overflow-hidden rounded-lg border border-navy-100 text-center">
            <div className="bg-navy-50 p-1 text-[11px] font-bold uppercase text-navy-400">
              Predicted
            </div>
            <div className="bg-navy-50 p-1 text-[11px] font-bold uppercase text-navy-400">
              non-match / match
            </div>
            <div className="border-t border-navy-100 bg-white p-4">
              <div className="text-2xl font-bold tabular-nums text-navy-800">{cm.tn}</div>
              <div className="mt-1 text-[11px] font-semibold text-navy-400">True non-matches</div>
            </div>
            <div className="border-t border-l border-navy-100 bg-red-50/60 p-4">
              <div className="text-2xl font-bold tabular-nums text-red-600">{cm.fp}</div>
              <div className="mt-1 text-[11px] font-semibold text-red-500">False positives</div>
            </div>
            <div className="border-t border-navy-100 bg-red-50/60 p-4">
              <div className="text-2xl font-bold tabular-nums text-red-600">{cm.fn}</div>
              <div className="mt-1 text-[11px] font-semibold text-red-500">False negatives</div>
            </div>
            <div className="border-t border-l border-navy-100 bg-brand-teal-light/60 p-4">
              <div className="text-2xl font-bold tabular-nums text-brand-teal-dark">{cm.tp}</div>
              <div className="mt-1 text-[11px] font-semibold text-brand-teal-dark">True matches found</div>
            </div>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-navy-500">
            Test support: {test.support.positive} true duplicate pairs and{" "}
            {test.support.negative} non-match pairs. A false positive costs analyst
            review time; a false negative means a duplicate stays hidden - which is
            why ambiguous pairs are always routed to human review.
          </p>
        </section>

        {/* Baseline comparison */}
        <section className="card p-5" aria-labelledby="baseline-heading">
          <h2 id="baseline-heading" className="text-sm font-bold uppercase tracking-wide text-navy-500">
            Baseline vs trained model
          </h2>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="border-b border-navy-100 text-left text-[11px] font-bold uppercase tracking-wide text-navy-400">
                <th scope="col" className="pb-2">Approach</th>
                <th scope="col" className="pb-2 text-right">Precision</th>
                <th scope="col" className="pb-2 text-right">Recall</th>
                <th scope="col" className="pb-2 text-right">F1</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-navy-50">
                <td className="py-2.5 pr-4 text-navy-600">{metrics.baseline.rule}</td>
                <td className="py-2.5 pl-4 text-right tabular-nums text-navy-600">{base.precision.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right tabular-nums text-navy-600">{base.recall.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right font-semibold tabular-nums text-navy-600">{base.f1.toFixed(3)}</td>
              </tr>
              <tr>
                <td className="py-2.5 pr-4 font-semibold text-navy-900">
                  Trained classifier
                  <span className="ml-2 rounded bg-brand-teal-light px-1.5 py-0.5 text-[10px] font-bold uppercase text-brand-teal-dark">
                    +{(test.f1 - base.f1).toFixed(3)} F1
                  </span>
                </td>
                <td className="py-2.5 pl-4 text-right font-bold tabular-nums text-brand-teal-dark">{test.precision.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right font-bold tabular-nums text-brand-teal-dark">{test.recall.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right font-bold tabular-nums text-brand-teal-dark">{test.f1.toFixed(3)}</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-4 text-xs leading-relaxed text-navy-500">
            Both approaches are evaluated on the same held-out pairs. The trained
            model recovers {test.recall >= 0.99 ? "every" : "nearly every"} true
            duplicate the rule-based baseline misses.
          </p>

          <h3 className="mt-5 text-xs font-bold uppercase tracking-wide text-navy-400">
            Recommendation bands
          </h3>
          <div className="mt-2 space-y-1.5 text-xs text-navy-600">
            <p>
              <strong className="text-brand-teal-dark">Likely match</strong> — score ≥{" "}
              {metrics.thresholds.likely}: high-confidence duplicate, still requires
              your confirmation.
            </p>
            <p>
              <strong className="text-amber-600">Needs review</strong> — score{" "}
              {metrics.thresholds.review_lower}–{metrics.thresholds.likely}: mixed
              evidence, human judgment required.
            </p>
            <p>
              <strong className="text-navy-600">Unlikely match</strong> — score &lt;{" "}
              {metrics.thresholds.review_lower}: distinct records.
            </p>
          </div>
        </section>
      </div>

      {/* How matching works */}
      <section className="card mt-6 p-5" aria-labelledby="how-heading">
        <h2 id="how-heading" className="text-sm font-bold uppercase tracking-wide text-navy-500">
          How matching works
        </h2>
        <ol className="mt-4 grid gap-3 text-sm text-navy-600 md:grid-cols-2">
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">1</span>
            <span>
              <strong className="text-navy-900">Normalize.</strong> Names, websites,
              addresses and locations are standardized (case, punctuation, legal
              suffixes, URL forms) while originals are preserved for display.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">2</span>
            <span>
              <strong className="text-navy-900">Retrieve candidates.</strong> A
              character n-gram TF-IDF + SVD embedding powers FAISS nearest-neighbour
              search (top {metrics.candidate_generation.top_k} per record), unioned
              with deterministic website/location blocking - avoiding brute-force
              all-pairs comparison.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">3</span>
            <span>
              <strong className="text-navy-900">Score with evidence.</strong> A
              logistic-regression classifier combines {metrics.model.feature_names.length}{" "}
              interpretable pair features into a 0–100% match score with per-field
              evidence shown for every suggestion.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">4</span>
            <span>
              <strong className="text-navy-900">Human review.</strong> Scores map to
              recommendation bands; only your explicit decision is recorded. Records
              are never merged automatically.
            </span>
          </li>
        </ol>

        <details className="mt-5 rounded-lg border border-navy-100 bg-navy-50/50 p-4">
          <summary className="cursor-pointer text-sm font-bold text-navy-800">
            Feature definitions ({metrics.model.feature_names.length} features)
          </summary>
          <div className="mt-3 overflow-x-auto scroll-thin">
            <table className="w-full min-w-[520px] text-left text-xs">
              <thead>
                <tr className="border-b border-navy-100 text-[10px] font-bold uppercase tracking-wide text-navy-400">
                  <th scope="col" className="pb-2 pr-4">Feature</th>
                  <th scope="col" className="pb-2">Meaning</th>
                </tr>
              </thead>
              <tbody>
                {metrics.model.feature_names.map((f) => (
                  <tr key={f} className="border-b border-navy-50 last:border-0">
                    <td className="py-1.5 pr-4 font-mono font-semibold text-navy-800">{f}</td>
                    <td className="py-1.5 text-navy-600">{FEATURE_EXPLANATIONS[f] ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      {/* Provenance footer */}
      <section className="card mt-6 bg-navy-900 p-5 text-white">
        <h2 className="text-sm font-bold uppercase tracking-wide text-navy-300">
          Benchmark methodology
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-navy-100">
          {metrics.qualification} Dataset: {metrics.dataset.records} synthetic records
          across {metrics.dataset.entities} canonical entities (seed{" "}
          {metrics.dataset.seed}), split by entity so no supplier appears in both
          training and test. Experiment tracking: MLflow runs{" "}
          <span className="font-mono text-xs">{metrics.mlflow.baseline_run_id.slice(0, 8)}</span>{" "}
          (baseline) and{" "}
          <span className="font-mono text-xs">{metrics.mlflow.model_run_id.slice(0, 8)}</span>{" "}
          (model).
        </p>
        <div className="mt-4 flex flex-wrap gap-4 text-xs font-semibold">
          <a className="text-brand-teal-light underline-offset-2 hover:underline" href={`${GITHUB_BASE}/docs/ML_METHODOLOGY.md`} target="_blank" rel="noopener noreferrer">
            ML methodology →
          </a>
          <a className="text-brand-teal-light underline-offset-2 hover:underline" href={`${GITHUB_BASE}/reports/model_evaluation.md`} target="_blank" rel="noopener noreferrer">
            Full evaluation report →
          </a>
          <a className="text-brand-teal-light underline-offset-2 hover:underline" href={`${GITHUB_BASE}/docs/SECURITY_AND_LIMITATIONS.md`} target="_blank" rel="noopener noreferrer">
            Security &amp; limitations →
          </a>
        </div>
      </section>
    </div>
  );
}
