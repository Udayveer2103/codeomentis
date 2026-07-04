import { useQuery } from "@tanstack/react-query";
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