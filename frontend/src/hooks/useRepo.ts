import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Repo, RepoStatus, IngestionProgress } from "@/types";

async function fetchRepo(repoId: string): Promise<Repo> {
  return await api.get<Repo>(`/api/repos/${repoId}`);
}

export function useRepo(repoId: string) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["repo", repoId],
    queryFn: () => fetchRepo(repoId),
    enabled: !!repoId,
    staleTime: 30_000,
  });

  return {
    repo: data ?? null,
    loading: isLoading,
    error: error ?? null,
  };
}

const TERMINAL_STAGES = new Set(["ready", "error"]);
const INGESTING_STATUSES = new Set<RepoStatus>(["pending", "indexing"]);
const POLL_INTERVAL_MS = 2_000;

async function fetchProgress(repoId: string): Promise<IngestionProgress | null> {
  return await api.get<IngestionProgress | null>(`/api/repos/${repoId}/progress`);
}

// Polls the new GET /api/repos/{repo_id}/progress endpoint via TanStack
// Query's own refetchInterval — no setInterval, no EventSource/SSE, no
// separate state-management mechanism. Polling starts only while the
// parent repo's status is pending/indexing, and self-stops the moment
// a terminal stage (ready/error) comes back, via refetchInterval
// returning false. On that same terminal frame it also invalidates the
// ["repo", repoId] query so the rest of the page (which reads
// repo.status from useRepo above) picks up the change without a
// separate poll of its own.
export function useIngestionProgress(repoId: string, status: RepoStatus | undefined) {
  const queryClient = useQueryClient();
  const isIngesting = !!status && INGESTING_STATUSES.has(status);

  const { data } = useQuery({
    queryKey: ["repo-progress", repoId],
    queryFn: () => fetchProgress(repoId),
    enabled: !!repoId && isIngesting,
    staleTime: 0,
    refetchInterval: (query) => {
      const stage = query.state.data?.stage;

      if (stage && TERMINAL_STAGES.has(stage)) {
        queryClient.invalidateQueries({ queryKey: ["repo", repoId] });
        return false;
      }

      return isIngesting ? POLL_INTERVAL_MS : false;
    },
  });

  return { progress: data ?? null };
}