import { useCallback, useEffect, useState } from "react";
import type { AnalysisSummary, ModelMetrics } from "./api/types";
import {
  createDemoAnalysis,
  getAnalysis,
  getModelMetrics,
  toRequestError,
} from "./api/client";
import Header from "./components/Header";
import Footer from "./components/Footer";
import Overview from "./views/Overview";
import UploadView from "./views/UploadView";
import ReviewWorkspace from "./views/ReviewWorkspace";
import ModelEvidence from "./views/ModelEvidence";

export type ViewId = "overview" | "upload" | "review" | "model";

const STORAGE_KEY = "vendorlens:activeAnalysis";

interface Toast {
  id: number;
  message: string;
  tone: "success" | "error";
}

export default function App() {
  const [view, setView] = useState<ViewId>("overview");
  const [analysis, setAnalysis] = useState<AnalysisSummary | null>(null);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [exploring, setExploring] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((message: string, tone: "success" | "error") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  // Load model metrics once for the overview teaser.
  useEffect(() => {
    getModelMetrics()
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, []);

  // Restore the last active analysis after a page reload.
  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    getAnalysis(saved)
      .then(setAnalysis)
      .catch(() => window.localStorage.removeItem(STORAGE_KEY));
  }, []);

  const activate = useCallback((summary: AnalysisSummary) => {
    setAnalysis(summary);
    window.localStorage.setItem(STORAGE_KEY, summary.analysis_id);
  }, []);

  const exploreSample = useCallback(async () => {
    setExploring(true);
    try {
      const summary = await createDemoAnalysis();
      activate(summary);
      setView("review");
      notify(
        `Sample analyzed: ${summary.counts.records} records, ${summary.counts.suggestions} candidate pairs.`,
        "success",
      );
    } catch (err) {
      notify(toRequestError(err).message, "error");
    } finally {
      setExploring(false);
    }
  }, [activate, notify]);

  return (
    <div className="flex min-h-screen flex-col bg-brand-paper">
      <Header active={view} onNavigate={setView} apiDocsUrl="/docs" />

      <main className="flex-1">
        {view === "overview" && (
          <Overview
            analysis={analysis}
            metrics={metrics}
            onExploreSample={exploreSample}
            onUpload={() => setView("upload")}
            onReview={() => setView("review")}
            onModel={() => setView("model")}
            exploring={exploring}
          />
        )}
        {view === "upload" && (
          <UploadView
            onAnalyzed={(summary) => {
              activate(summary);
              setView("review");
              notify(
                `Analysis complete: ${summary.counts.suggestions} candidate pairs found.`,
                "success",
              );
            }}
          />
        )}
        {view === "review" && (
          <ReviewWorkspace
            analysis={analysis}
            onAnalysisRefreshed={setAnalysis}
            onGoUpload={() => setView("upload")}
            notify={notify}
          />
        )}
        {view === "model" && <ModelEvidence />}
      </main>

      {/* Toasts */}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto max-w-sm rounded-lg px-4 py-3 text-sm font-semibold shadow-lg ${
              t.tone === "success"
                ? "bg-navy-900 text-white"
                : "bg-red-600 text-white"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>

      <Footer />
    </div>
  );
}
