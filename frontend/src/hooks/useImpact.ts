// hooks/useImpact.ts  —  RepoMind Week 3
// TanStack Query hooks for the Impact Analyzer feature

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

export interface ImpactResult {
  query_node: string;
  nodes: ImpactNode[];
  links: ImpactLink[];
  total_impacted: number;
  graph_stats: {
    total_nodes: number;
    total_edges: number;
  };
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