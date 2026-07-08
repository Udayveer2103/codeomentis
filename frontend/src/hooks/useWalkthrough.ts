// hooks/useWalkthrough.ts — RepoMind Week 4
//
// TanStack Query hook for the Onboarding Walkthrough feature.
// Mirrors the pattern established in useHeatmap.ts / useImpact.ts.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface WalkthroughStep {
  // NOTE: id is only present on cached responses (SELECT * from
  // walkthrough_steps). Freshly-generated responses build rows in-memory
  // and never receive the DB-assigned id back from the insert RPC, so it
  // is genuinely absent on that path — not a defensive assumption.
  // Do NOT use `id` as a React key; use step_order (see WalkthroughStepCard).
  id?: string;
  step_order: number;
  file_path: string;
  function_name: string | null;
  title: string;
  description: string;
  reason: string;
  in_degree: number;
  out_degree: number;
  bfs_level: number;
}

export interface WalkthroughResult {
  repo_id: string;
  steps: WalkthroughStep[];
  cached: boolean;
}

// ── API call ───────────────────────────────────────────────────────────────────

async function fetchWalkthrough(repoId: string): Promise<WalkthroughResult> {
  return api.get<WalkthroughResult>(`/api/walkthrough/${repoId}`);
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useWalkthrough(repoId: string) {
  return useQuery({
    queryKey: ["walkthrough", repoId],
    queryFn: () => fetchWalkthrough(repoId),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5, // 5 minutes — walkthrough is cached server-side and doesn't change often
    retry: false,
  });
}