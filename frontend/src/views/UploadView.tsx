import { useRef, useState } from "react";
import type { AnalysisSummary } from "../api/types";
import { RequestError, toRequestError, uploadCsv } from "../api/client";
import { InlineSpinner } from "../components/Loading";

interface UploadViewProps {
  onAnalyzed: (summary: AnalysisSummary) => void;
}

const SCHEMA_ROWS = [
  { name: "supplier_id", required: true, type: "string", description: "Unique record identifier within the file" },
  { name: "supplier_name", required: true, type: "string", description: "Supplier display name (compared after normalization)" },
  { name: "street_address", required: false, type: "string", description: "Street address" },
  { name: "city", required: false, type: "string", description: "City name" },
  { name: "state", required: false, type: "string", description: "State or region code" },
  { name: "postal_code", required: false, type: "string", description: "Postal / ZIP code" },
  { name: "country", required: false, type: "string", description: "Country name" },
  { name: "website", required: false, type: "string", description: "Website URL or domain" },
];

export default function UploadView({ onAnalyzed }: UploadViewProps) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<RequestError | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setError(null);
    setFileName(file.name);
    setBusy(true);
    try {
      const summary = await uploadCsv(file);
      onAnalyzed(summary);
    } catch (err) {
      setError(err instanceof RequestError ? err : toRequestError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
      <h1 className="text-2xl font-bold tracking-tight text-navy-900">
        Upload Supplier CSV
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-navy-600">
        Import a supplier register and run duplicate detection. Files are validated
        against the schema below before any analysis, and nothing is merged - every
        recommendation waits for a human decision.
      </p>

      {/* Dropzone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload CSV file"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) void handleFile(file);
        }}
        className={`mt-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal ${
          dragging
            ? "border-brand-teal bg-brand-teal-light/50"
            : "border-navy-200 bg-white hover:border-navy-300 hover:bg-navy-50/50"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" className="text-navy-300" aria-hidden="true">
          <path
            d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {busy ? (
          <div className="mt-4">
            <InlineSpinner label={`Analyzing ${fileName}…`} />
          </div>
        ) : (
          <>
            <p className="mt-4 text-sm font-semibold text-navy-800">
              Drag &amp; drop your CSV here, or click to browse
            </p>
            <p className="mt-1 text-xs text-navy-400">
              .csv files only · max 5 MB · max 2,000 supplier rows · UTF-8
            </p>
          </>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4"
        >
          <p className="text-sm font-bold text-red-800">{error.message}</p>
          {error.details.length > 0 && (
            <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs text-red-700">
              {error.details.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-4 flex items-center gap-2 text-sm">
        <span className="text-navy-500">Need a starting point?</span>
        <a
          href="/api/v1/demo/sample"
          className="font-semibold text-brand-teal-dark underline-offset-2 hover:underline"
          download
        >
          Download the sample supplier CSV
        </a>
      </div>

      {/* Schema */}
      <section className="mt-10" aria-labelledby="schema-heading">
        <h2 id="schema-heading" className="text-lg font-bold text-navy-900">
          Expected file format
        </h2>
        <div className="card mt-4 overflow-hidden">
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-navy-100 bg-navy-50/70 text-[11px] font-bold uppercase tracking-wide text-navy-500">
                  <th scope="col" className="px-4 py-3">Column</th>
                  <th scope="col" className="px-4 py-3">Required</th>
                  <th scope="col" className="px-4 py-3">Type</th>
                  <th scope="col" className="px-4 py-3">Description</th>
                </tr>
              </thead>
              <tbody>
                {SCHEMA_ROWS.map((row) => (
                  <tr key={row.name} className="border-b border-navy-50 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-xs font-semibold text-navy-900">
                      {row.name}
                    </td>
                    <td className="px-4 py-2.5">
                      {row.required ? (
                        <span className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-bold text-red-700">
                          Required
                        </span>
                      ) : (
                        <span className="rounded bg-navy-50 px-1.5 py-0.5 text-[11px] font-bold text-navy-500">
                          Optional
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-navy-600">{row.type}</td>
                    <td className="px-4 py-2.5 text-navy-600">{row.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-navy-400">
          Optional fields that are missing are recorded as missing - they never count
          as evidence for or against a match. Unknown columns are ignored and reported
          back to you as warnings.
        </p>
      </section>
    </div>
  );
}
