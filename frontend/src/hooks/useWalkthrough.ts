// hooks/useWalkthrough.ts — RepoMind Walkthrough Redesign
//
// TanStack Query hook for the Onboarding Walkthrough feature.
// Mirrors the pattern established in useHeatmap.ts / useImpact.ts.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

// Six-role taxonomy (deterministic, heuristic-first classification on the
// backend — see services/walkthrough.py::_classify_role).
export type WalkthroughRole =
| "authentication"
| "application_shell"
| "api"
| "feature"
| "business_logic"
| "utility";

// Entry shape for `called_by` / `calls`, resolved from the in-memory call
// graph at generation time.
export interface WalkthroughRelation {
function_name: string;
file_path: string;
}

export interface WalkthroughStep {
// Only present on cached responses (SELECT * from walkthrough_steps).
// Freshly-generated responses build rows in-memory and never receive the
// DB-assigned id back from the insert RPC.
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

role: WalkthroughRole;
group_label: string;

// Response-only — never persisted. Present on a freshly-generated
// response; absent when cached: true.
called_by?: WalkthroughRelation[];
calls?: WalkthroughRelation[];
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