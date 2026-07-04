import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Repo } from "@/types";

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