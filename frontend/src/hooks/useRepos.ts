import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Repo } from "@/types";

interface ReposResponse {
  repos: Repo[];
}

async function fetchRepos(): Promise<ReposResponse> {
  return await api.get<ReposResponse>("/api/repos");
}

export function useRepos() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["repos"],
    queryFn: fetchRepos,
    staleTime: 30_000,
  });

  return {
    repos: data?.repos ?? [],
    loading: isLoading,
    error: error ?? null,
  };
}

// Removes a repository (and its RepoMind data) from the current user's
// account — never touches the underlying GitHub repository itself.
export function useDeleteRepo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repoId: string) => api.delete(`/api/repos/${repoId}`),
    onSuccess: (_data, repoId) => {
      queryClient.removeQueries({ queryKey: ["repo", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
}