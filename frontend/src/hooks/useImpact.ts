// hooks/useImpact.ts — CodeoMentis Week 3
// TanStack Query hooks for the Impact Analyzer feature
//
// Milestone 5: ImpactResult extended with the AI reasoning fields
// (Milestone 2) and deterministic fields (Milestone 3) the backend
// has returned since those milestones. All nine fields are typed
// here; only ai_summary, safe_to_change, and risk_level are rendered
// as of Milestone 5 — risk_reasons, possible_regressions,
// suggested_test_cases, refactoring_advice, affected_files, and
// downstream_call_chain are typed for correctness but not yet
// consumed by any component (Milestone 6/7).
//
// fetchImpact/useImpactAnalysis themselves are unchanged: same
// query key, same endpoint, same staleTime/retry behavior.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ImpactNode {
  id: string;
  file_path: string;
  function_name: string;
  depth: number;
}

export interface ImpactLink {
  source: string;
  target: string;
  depth: number;
}

export type RiskLevel = "low" | "medium" | "high";

export interface CallChainEntry {
  file_path: string;
  function_name: string;
  depth: number;
}

export interface DownstreamCallChain {
  entry_point: {
    file_path: string;
    function_name: string;
  };
  chain: CallChainEntry[];
}

export interface ImpactResult {
  query_node: string;
  nodes: ImpactNode[];
  links: ImpactLink[];
  total_impacted: number;
  graph_stats: {
    total_nodes: number;
    total_edges: number;
  };

  // Milestone 3 — deterministic, always present (never null), full/unbounded
  affected_files: string[];
  downstream_call_chain: DownstreamCallChain[];

  // Milestone 2 — AI reasoning, all nullable per the backend's fail-soft
  // contract (LLM unavailable or validation failure → every field below
  // is null, graph/deterministic fields above are still always populated)
  ai_summary: string | null;
  safe_to_change: boolean | null;
  risk_level: RiskLevel | null;
  risk_reasons: string[] | null;
  possible_regressions: string[] | null;
  suggested_test_cases: string[] | null;
  refactoring_advice: string | null;
}

export interface FunctionOption {
  id: string;
  file_path: string;
  function_name: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function fetchImpact(
  repoId: string,
  functionId: string,
  maxDepth: number
): Promise<ImpactResult> {
  const params = new URLSearchParams({
    function: functionId,
    max_depth: String(maxDepth),
  });
  return await api.get<ImpactResult>(
    `/api/impact/${repoId}?${params}`
  );
}

async function fetchFunctions(
  repoId: string,
  search: string
): Promise<FunctionOption[]> {
  const params = new URLSearchParams({ search, limit: "60" });
  const res = await api.get<{ functions: FunctionOption[] }>(
    `/api/impact/${repoId}/functions?${params}`
  );

  return res.functions ?? [];
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useImpactAnalysis(
  repoId: string,
  functionId: string | null,
  maxDepth: number = 5
) {
  return useQuery({
    queryKey: ["impact", repoId, functionId, maxDepth],
    queryFn: () => fetchImpact(repoId, functionId!, maxDepth),
    enabled: !!repoId && !!functionId,
    staleTime: 1000 * 60 * 5, // 5 minutes — graph data doesn't change often
    retry: false,
  });
}

export function useFunctionList(repoId: string, search: string) {
  return useQuery({
    queryKey: ["impact-functions", repoId, search],
    queryFn: () => fetchFunctions(repoId, search),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 10,
    placeholderData: (prev) => prev, // keep previous results while fetching
  });
}