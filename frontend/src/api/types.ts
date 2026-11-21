/** API contract types mirroring the FastAPI Pydantic schemas. */

export type ReviewDecisionValue = "confirm_same" | "reject_match" | "needs_investigation";
export type Band = "likely_match" | "needs_review" | "unlikely_match";

export interface AnalysisCounts {
  records: number;
  suggestions: number;
  likely: number;
  needs_review: number;
  unlikely: number;
  reviewed: number;
  confirmed: number;
  rejected: number;
  investigation: number;
}

export interface AnalysisSummary {
  analysis_id: string;
  source_type: "sample" | "upload";
  filename: string | null;
  created_at: string;
  row_count: number;
  model_version: string;
  status: string;
  counts: AnalysisCounts;
  warnings: string[];
}

export interface RecordBrief {
  supplier_id: string;
  supplier_name: string;
  street_address: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  website: string | null;
  normalized_name: string | null;
}

export interface MatchSignals {
  name_similarity: number;
  name_evidence: "strong" | "moderate" | "weak";
  token_jaccard: number;
  legal_suffix: "same" | "different" | "missing";
  city: "same" | "different" | "missing";
  state: "same" | "different" | "missing";
  postal_code: "same" | "different" | "missing";
  website: "same" | "different" | "missing";
  address_similarity: number | "missing";
}

export interface ReviewDecision {
  decision: ReviewDecisionValue;
  notes: string | null;
  reviewed_at: string | null;
}

export interface MatchSuggestionItem {
  suggestion_id: string;
  score: number;
  band: Band;
  signals: MatchSignals;
  left: RecordBrief;
  right: RecordBrief;
  review_decision: ReviewDecision | null;
}

export interface MatchesPage {
  total: number;
  items: MatchSuggestionItem[];
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_version: string | null;
  app_version: string;
  retrieval_engine: string;
  database: string;
}

export interface DemoInfo {
  available: boolean;
  record_count: number;
  description: string;
  provenance: string;
  sample_download_path: string;
}

export interface SplitInfo {
  entities: number;
  records: number;
}

export interface MetricBlock {
  precision: number;
  recall: number;
  f1: number;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  false_positives: number;
  false_negatives: number;
  support: { positive: number; negative: number };
}

export interface ModelMetrics {
  model_version: string;
  generated_at: string;
  dataset: { provenance: string; seed: number; records: number; entities: number; path: string };
  splits: { strategy: string; train: SplitInfo; val: SplitInfo; test: SplitInfo };
  baseline: { rule: string; val: MetricBlock; test: MetricBlock };
  model: { type: string; feature_names: string[]; val: MetricBlock; test: MetricBlock };
  thresholds: { decision: number; likely: number; review_lower: number; selection_basis: string };
  candidate_generation: {
    engine: string;
    top_k: number;
    blocking: string;
    candidate_recall: { val: number; test: number };
  };
  difficult_cases: {
    false_positives: { left: string; right: string; score: number }[];
    false_negatives: { left: string; right: string; score: number }[];
  };
  mlflow: { tracking_uri: string; experiment: string; baseline_run_id: string; model_run_id: string };
  environment: Record<string, string>;
  qualification: string;
  figures?: string[];
}

export interface ApiError {
  code: string;
  message: string;
  details: string[];
}
