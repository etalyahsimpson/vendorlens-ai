/** Typed Axios client for the VendorLens backend API. */

import axios, { AxiosError } from "axios";
import type {
  AnalysisSummary,
  ApiError,
  DemoInfo,
  HealthResponse,
  MatchSuggestionItem,
  MatchesPage,
  ModelMetrics,
  ReviewDecisionValue,
} from "./types";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120_000,
});

export class RequestError extends Error {
  code: string;
  details: string[];

  constructor(message: string, code = "request_failed", details: string[] = []) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

/** Normalize axios/API failures into a single friendly error type. */
export function toRequestError(err: unknown): RequestError {
  if (err instanceof AxiosError) {
    const detail = err.response?.data as { error?: ApiError; detail?: unknown } | undefined;
    if (detail?.error) {
      return new RequestError(detail.error.message, detail.error.code, detail.error.details);
    }
    if (typeof detail?.detail === "string") {
      return new RequestError(detail.detail, "validation_error");
    }
    if (err.code === "ECONNABORTED") {
      return new RequestError(
        "The request timed out. Large files may take a minute to analyze.",
        "timeout",
      );
    }
    if (!err.response) {
      return new RequestError(
        "Could not reach the VendorLens backend. Is it running?",
        "network_error",
      );
    }
    return new RequestError(
      `Request failed (${err.response.status}).`,
      `http_${err.response.status}`,
    );
  }
  return new RequestError("Unexpected error. Please try again.");
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function getDemoInfo(): Promise<DemoInfo> {
  const { data } = await api.get<DemoInfo>("/demo");
  return data;
}

export async function createDemoAnalysis(): Promise<AnalysisSummary> {
  const { data } = await api.post<AnalysisSummary>("/analyses/demo");
  return data;
}

export async function uploadCsv(file: File): Promise<AnalysisSummary> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<AnalysisSummary>("/analyses/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getAnalysis(id: string): Promise<AnalysisSummary> {
  const { data } = await api.get<AnalysisSummary>(`/analyses/${id}`);
  return data;
}

export async function getMatches(
  id: string,
  params: {
    band?: string;
    decision?: string;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<MatchesPage> {
  const { data } = await api.get<MatchesPage>(`/analyses/${id}/matches`, { params });
  return data;
}

export async function reviewMatch(
  suggestionId: string,
  decision: ReviewDecisionValue,
  notes?: string,
): Promise<MatchSuggestionItem> {
  const { data } = await api.patch<MatchSuggestionItem>(
    `/matches/${suggestionId}/review`,
    { decision, notes: notes ?? null },
  );
  return data;
}

export function exportUrl(id: string): string {
  return `/api/v1/analyses/${id}/export`;
}

export async function getModelMetrics(): Promise<ModelMetrics> {
  const { data } = await api.get<ModelMetrics>("/model/metrics");
  return data;
}
