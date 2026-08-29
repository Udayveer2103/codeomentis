// pages/HeatmapPage.tsx  —  CodeoMentis Week 3
//
// Tech Debt Heatmap page.
// URL: /repo/:repoId/heatmap
//
// Design: matches Dashboard / Login neutral-950 system (not ImpactAnalyzer's slate-*)
//
// Layout:
//   Header bar  — back link, title, sort selector
//   Summary row — 5 stat chips (total, high, medium, low, avg score)
//   Filter bar  — severity chips (All / High / Medium / Low)
//   Table       — sortable file rows with inline sub-score bars
//   Drawer      — slides in from right on row click, shows full breakdown

import { useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Flame, ChevronUp, ChevronDown, X, FileCode } from "lucide-react";
import {
  useHeatmap,
  DEFAULT_FILTERS,
  type HeatmapFilters,
  type FileScore,
  type Severity,
  type SortField,
} from "@/hooks/useHeatmap";

// ── Sub-components ─────────────────────────────────────────────────────────────

// Inline horizontal bar, 0–100 value
function ScoreBar({
  value,
  color,
}: {
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5 rounded-full bg-neutral-800 overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="text-xs text-neutral-500 tabular-nums w-8 text-right">
        {value.toFixed(0)}
      </span>
    </div>
  );
}

// Severity badge
function SeverityBadge({ severity }: { severity: FileScore["severity"] }) {
  const styles = {
    high:   "text-red-400 bg-red-950/40 border-red-900/50",
    medium: "text-yellow-400 bg-yellow-950/40 border-yellow-900/50",
    low:    "text-neutral-400 bg-neutral-800 border-neutral-700",
  };
  return (
    <span
      className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${styles[severity]}`}
    >
      {severity}
    </span>
  );
}

// Sort indicator icon
function SortIcon({
  field,
  current,
  direction,
}: {
  field: SortField;
  current: SortField;
  direction: "asc" | "desc";
}) {
  if (field !== current) {
    return <ChevronDown className="w-3 h-3 text-neutral-700" />;
  }
  return direction === "desc"
    ? <ChevronDown className="w-3 h-3 text-brand-400" />
    : <ChevronUp className="w-3 h-3 text-brand-400" />;
}

// ── File detail drawer ─────────────────────────────────────────────────────────

function FileDrawer({
  file,
  onClose,
}: {
  file: FileScore;
  onClose: () => void;
}) {
  const subScores: { label: string; value: number; description: string; color: string }[] = [
    {
      label: "Cyclomatic Complexity",
      value: file.cc_score,
      description: "Branch density — if/else/for/while/&&/||. Python uses radon; JS/TS uses keyword heuristic.",
      color: "bg-purple-500",
    },
    {
      label: "Coupling",
      value: file.coupling_score,
      description: "How many other files import this file. High coupling = risky to change.",
      color: "bg-sky-500",
    },
    {
      label: "TODO Density",
      value: file.todo_density,
      description: "Count of TODO / FIXME / HACK / XXX markers relative to line count.",
      color: "bg-amber-500",
    },
    {
      label: "Function Length",
      value: file.fn_length_score,
      description: "Average function length normalised against 80-line threshold.",
      color: "bg-orange-500",
    },
  ];

  // Composite formula weights — mirrors complexity.py exactly
  const weights = [0.35, 0.25, 0.20, 0.20];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-[400px] bg-neutral-900 border-l border-neutral-800 overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-neutral-800">
          <div className="min-w-0 flex-1 pr-3">
            <div className="flex items-center gap-2 mb-1">
              <FileCode className="w-4 h-4 text-brand-400 shrink-0" />
              <SeverityBadge severity={file.severity} />
            </div>
            <p className="font-mono text-sm text-white break-all leading-snug">
              {file.file_path}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-lg text-neutral-500 hover:text-white hover:bg-neutral-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Composite score */}
        <div className="p-5 border-b border-neutral-800">
          <div className="flex items-end gap-3">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-widest mb-1">
                Composite Score
              </p>
              <p className="text-4xl font-bold text-white tabular-nums">
                {file.composite_score.toFixed(1)}
              </p>
            </div>
            <div className="mb-1 text-xs text-neutral-600">/100</div>
          </div>
          {/* Full composite bar */}
          <div className="mt-3 w-full h-2 rounded-full bg-neutral-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-brand-500"
              style={{ width: `${file.composite_score}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-neutral-600">
            Weighted: 35% complexity · 25% coupling · 20% TODOs · 20% fn length
          </p>
        </div>

        {/* Sub-scores */}
        <div className="p-5 flex flex-col gap-5">
          {subScores.map((s, i) => (
            <div key={s.label}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-neutral-200">{s.label}</span>
                <span className="text-sm font-mono font-semibold text-white tabular-nums">
                  {s.value.toFixed(1)}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-neutral-800 overflow-hidden mb-1.5">
                <div
                  className={`h-full rounded-full ${s.color}`}
                  style={{ width: `${s.value}%` }}
                />
              </div>
              <p className="text-xs text-neutral-600">{s.description}</p>
              <p className="text-xs text-neutral-700 mt-0.5">
                Weight: {(weights[i] * 100).toFixed(0)}% of composite
              </p>
            </div>
          ))}
        </div>

        {/* File stats */}
        <div className="mx-5 mb-5 rounded-xl bg-neutral-950 border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500 uppercase tracking-widest mb-3">
            File Stats
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Lines", value: file.line_count.toLocaleString() },
              { label: "Functions", value: file.function_count },
              { label: "TODOs", value: file.todo_count },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-neutral-500 text-xs">{label}</p>
                <p className="text-white font-mono font-semibold">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-neutral-800">
            <p className="text-neutral-500 text-xs">Language</p>
            <p className="text-white font-mono text-sm capitalize">{file.language}</p>
          </div>
        </div>
      </div>
    </>
  );
}

// ── Column header button ───────────────────────────────────────────────────────

function ColHeader({
  label,
  field,
  currentSort,
  direction,
  onSort,
  className = "",
}: {
  label: string;
  field: SortField;
  currentSort: SortField;
  direction: "asc" | "desc";
  onSort: (f: SortField) => void;
  className?: string;
}) {
  return (
    <th
      className={`px-3 py-2.5 text-left cursor-pointer select-none hover:text-neutral-200 transition-colors ${className}`}
      onClick={() => onSort(field)}
    >
      <div className="flex items-center gap-1 text-xs font-medium text-neutral-500">
        {label}
        <SortIcon field={field} current={currentSort} direction={direction} />
      </div>
    </th>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function HeatmapPage() {
  const { repoId } = useParams<{ repoId: string }>();

  const [filters, setFilters] = useState<HeatmapFilters>(DEFAULT_FILTERS);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [selectedFile, setSelectedFile] = useState<FileScore | null>(null);

  const { data, isLoading, isError, error } = useHeatmap(repoId!, filters);

  // ── Sort handler — toggle direction if same field, reset to desc if new field
  const handleSort = useCallback(
    (field: SortField) => {
      if (field === filters.sort) {
        // Toggle direction — for file_path asc/desc are both meaningful;
        // for scores we only send one direction to the API (desc = hottest first)
        // so direction is purely a UI concern here, we re-request with same sort.
        setSortDirection((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setFilters((f) => ({ ...f, sort: field }));
        setSortDirection("desc");
      }
    },
    [filters.sort]
  );

  // ── Severity filter chips
  const severities: { label: string; value: Severity }[] = [
    { label: "All", value: "all" },
    { label: "High", value: "high" },
    { label: "Medium", value: "medium" },
    { label: "Low", value: "low" },
  ];

  // Client-side direction flip (API always returns desc; flip in-memory for asc)
  const displayFiles = (() => {
    if (!data?.files) return [];
    if (sortDirection === "asc") return [...data.files].reverse();
    return data.files;
  })();

  const summary = data?.summary;

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur">
        <div className="flex h-14 items-center gap-4 px-6 max-w-7xl mx-auto">
          <Link
            to={`/repo/${repoId}`}
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>

          <div className="flex items-center gap-2">
            <Flame className="w-4 h-4 text-brand-400" />
            <span className="font-display font-semibold text-white">
              Tech Debt Heatmap
            </span>
          </div>
        </div>
      </header>

      <main className="flex-1 px-6 py-6 max-w-7xl mx-auto w-full">

        {/* ── Summary chips ────────────────────────────────────────────────── */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
            {[
              {
                label: "Total files",
                value: summary.total_files.toLocaleString(),
                sub: "scored",
                color: "text-white",
              },
              {
                label: "High risk",
                value: summary.high_count,
                sub: "files",
                color: summary.high_count > 0 ? "text-red-400" : "text-neutral-500",
              },
              {
                label: "Medium risk",
                value: summary.medium_count,
                sub: "files",
                color: summary.medium_count > 0 ? "text-yellow-400" : "text-neutral-500",
              },
              {
                label: "Low risk",
                value: summary.low_count,
                sub: "files",
                color: "text-neutral-400",
              },
              {
                label: "Avg score",
                value: summary.avg_composite.toFixed(1),
                sub: `/ ${summary.max_composite.toFixed(1)} max`,
                color: "text-brand-400",
              },
            ].map(({ label, value, sub, color }) => (
              <div
                key={label}
                className="rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-3"
              >
                <p className="text-xs text-neutral-500 mb-1">{label}</p>
                <p className={`text-2xl font-bold font-display tabular-nums ${color}`}>
                  {value}
                </p>
                <p className="text-xs text-neutral-600 mt-0.5">{sub}</p>
              </div>
            ))}
          </div>
        )}

        {/* ── Severity filter bar ───────────────────────────────────────────── */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-neutral-600 mr-1">Show:</span>
          {severities.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setFilters((f) => ({ ...f, severity: value }))}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filters.severity === value
                  ? "bg-brand-500 text-white"
                  : "bg-neutral-800 text-neutral-400 hover:text-white hover:bg-neutral-700"
              }`}
            >
              {label}
              {summary && value !== "all" && (
                <span className="ml-1.5 opacity-60">
                  {value === "high"
                    ? summary.high_count
                    : value === "medium"
                    ? summary.medium_count
                    : summary.low_count}
                </span>
              )}
            </button>
          ))}

          {data && (
            <span className="ml-auto text-xs text-neutral-600">
              {displayFiles.length.toLocaleString()} file
              {displayFiles.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* ── Loading skeleton ──────────────────────────────────────────────── */}
        {isLoading && (
          <div className="space-y-2">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="h-12 rounded-lg bg-neutral-900 border border-neutral-800 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* ── Error ────────────────────────────────────────────────────────── */}
        {isError && (
          <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
            {(error as any)?.response?.data?.detail ?? "Failed to load heatmap data"}
          </div>
        )}

        {/* ── Table ─────────────────────────────────────────────────────────── */}
        {data && !isLoading && (
          <>
            {displayFiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
                <Flame className="w-8 h-8 text-neutral-700" />
                <p className="text-sm text-neutral-500">
                  No files match the selected filter
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-neutral-800 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-900 border-b border-neutral-800">
                    <tr>
                      <ColHeader
                        label="File"
                        field="file_path"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[35%]"
                      />
                      <ColHeader
                        label="Score"
                        field="composite_score"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[10%]"
                      />
                      <ColHeader
                        label="Complexity"
                        field="cc_score"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[14%]"
                      />
                      <ColHeader
                        label="Coupling"
                        field="coupling_score"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[14%]"
                      />
                      <ColHeader
                        label="TODOs"
                        field="todo_density"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[14%]"
                      />
                      <ColHeader
                        label="Fn Length"
                        field="fn_length_score"
                        currentSort={filters.sort}
                        direction={sortDirection}
                        onSort={handleSort}
                        className="w-[13%]"
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {displayFiles.map((file, idx) => (
                      <tr
                        key={file.id}
                        onClick={() => setSelectedFile(file)}
                        className={`border-b border-neutral-800/60 cursor-pointer hover:bg-neutral-800/50 transition-colors ${
                          idx % 2 === 0 ? "bg-neutral-950" : "bg-neutral-900/30"
                        }`}
                      >
                        {/* File path */}
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <SeverityBadge severity={file.severity} />
                            <span
                              className="font-mono text-xs text-neutral-300 truncate"
                              title={file.file_path}
                            >
                              {file.file_path}
                            </span>
                          </div>
                        </td>

                        {/* Composite score — shown as number + mini bar */}
                        <td className="px-3 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="font-mono text-sm font-semibold text-white tabular-nums">
                              {file.composite_score.toFixed(1)}
                            </span>
                            <div className="w-12 h-1 rounded-full bg-neutral-800 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-brand-500"
                                style={{ width: `${file.composite_score}%` }}
                              />
                            </div>
                          </div>
                        </td>

                        {/* Sub-score bars */}
                        <td className="px-3 py-3">
                          <ScoreBar value={file.cc_score} color="bg-purple-500" />
                        </td>
                        <td className="px-3 py-3">
                          <ScoreBar value={file.coupling_score} color="bg-sky-500" />
                        </td>
                        <td className="px-3 py-3">
                          <ScoreBar value={file.todo_density} color="bg-amber-500" />
                        </td>
                        <td className="px-3 py-3">
                          <ScoreBar value={file.fn_length_score} color="bg-orange-500" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Footer: show limit warning if we hit the cap */}
                {displayFiles.length >= filters.limit && (
                  <div className="px-4 py-2.5 bg-neutral-900 border-t border-neutral-800 text-xs text-neutral-600 text-center">
                    Showing top {filters.limit} files.{" "}
                    <button
                      onClick={() => setFilters((f) => ({ ...f, limit: 500 }))}
                      className="text-brand-400 hover:text-brand-300 transition-colors"
                    >
                      Load up to 500
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      {/* ── File detail drawer ─────────────────────────────────────────────── */}
      {selectedFile && (
        <FileDrawer file={selectedFile} onClose={() => setSelectedFile(null)} />
      )}
    </div>
  );
} 