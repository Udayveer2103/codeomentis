// hooks/useHeatmap.ts  — CodeoMentis Week 3
//
// TanStack Query hook for the Tech Debt Heatmap feature.
// Mirrors the pattern established in useImpact.ts.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

export type Severity = "all" | "high" | "medium" | "low";

export type SortField =
  | "composite_score"
  | "cc_score"
  | "coupling_score"
  | "todo_density"
  | "fn_length_score"
  | "file_path";

export interface HeatmapFilters {
  severity: Severity;
  sort: SortField;
  limit: number;
}

export interface FileScore {
  id: string; // UUID — use as React key
  file_path: string;
  language: string;
  composite_score: number;
  cc_score: number;
  coupling_score: number;
  todo_density: number;
  fn_length_score: number;
  severity: "high" | "medium" | "low";
  line_count: number;
  function_count: number;
  todo_count: number;
}

export interface HeatmapSummary {
  total_files: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  avg_composite: number;
  max_composite: number;
}

export interface HeatmapResult {
  repo_id: string;
  summary: HeatmapSummary;
  files: FileScore[];
}

// ── Default filters ────────────────────────────────────────────────────────────

export const DEFAULT_FILTERS: HeatmapFilters = {
  severity: "all",
  sort: "composite_score",
  limit: 200,
};

// ── API call ───────────────────────────────────────────────────────────────────

async function fetchHeatmap(
  repoId: string,
  filters: HeatmapFilters
): Promise<HeatmapResult> {
  const params = new URLSearchParams({
    severity: filters.severity,
    sort: filters.sort,
    limit: String(filters.limit),
  });

  return api.get<HeatmapResult>(
    `/heatmap/${repoId}?${params.toString()}`
  );
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useHeatmap(
  repoId: string,
  filters: HeatmapFilters = DEFAULT_FILTERS
) {
  return useQuery({
    queryKey: ["heatmap", repoId, filters],
    queryFn: () => fetchHeatmap(repoId, filters),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: false,
  });
}