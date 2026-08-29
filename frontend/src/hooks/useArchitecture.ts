// hooks/useArchitecture.ts — CodeoMentis Architecture Analyzer
//
// TanStack Query hooks for the Repository Architecture Analyzer
// feature. One hook per endpoint, each independently cacheable —
// mirrors useHeatmap.ts / useWalkthrough.ts, and lets the page track
// fetch progress per-stage instead of behind one combined flag (see
// ArchitecturePage's StageTracker).

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────
// Field-for-field match to services/architecture_service.py,
// services/graph_adapter.py, and services/tech_detector.py's
// detect_tech_stack() — verified against the actual function bodies
// and routers/architecture.py, not guessed from the prose summary.

export type TechStackListField =
  | "frontend_framework"
  | "backend_framework"
  | "database"
  | "orm"
  | "authentication"
  | "styling"
  | "ai_providers"
  | "deployment";

export interface TechStack {
  languages: Record<string, number> | null;
  frontend_framework: string[] | null;
  backend_framework: string[] | null;
  database: string[] | null;
  orm: string[] | null;
  authentication: string[] | null;
  styling: string[] | null;
  ai_providers: string[] | null;
  deployment: string[] | null;
  package_manager: string | null;
}

export interface ArchitectureOverview {
  repository: string;
  architecture_pattern: string | null;
  tech_stack: TechStack | null;
  language_stats: Record<string, number> | null;
  file_count: number | null;
  config_file_count: number;
}

export interface ConfigFileEntry {
  path: string;
  purpose: string;
  category: string;
}

export interface ArchitectureConfigResult {
  repo_id: string;
  config_files: ConfigFileEntry[];
}

export interface FolderEntry {
  folder: string;
  file_count: number;
  responsibility: string | null;
}

export interface ArchitectureFoldersResult {
  repo_id: string;
  folders: FolderEntry[];
}

export type ArchitectureGraphView = "module" | "calls";

export interface ModuleNodeData {
  label: string;
  function_count: number;
}

export interface FunctionNodeData {
  label: string;
  file_path: string | null;
  language: string | null;
  in_degree: number;
  out_degree: number;
}

export interface ArchitectureGraphNode {
  id: string;
  type: "module" | "function";
  data: ModuleNodeData | FunctionNodeData;
}

export interface ArchitectureGraphEdge {
  id: string;
  source: string;
  target: string;
}

// NOTE: unlike every other architecture endpoint, GET /graph does NOT
// wrap its payload in {repo_id, ...} — get_graph_route() returns
// get_architecture_graph()'s result directly (confirmed against
// routers/architecture.py). Do not add a repo_id field here.
export interface ArchitectureGraphResult {
  nodes: ArchitectureGraphNode[];
  edges: ArchitectureGraphEdge[];
}

export interface ArchitectureSummaryResult {
  repo_id: string;
  summary: string | null;
  cached: boolean;
}

// ── Error helper ──────────────────────────────────────────────────────────────
// api.ts's request<T>() throws a bare Error built from the response
// body's `detail` field and does not preserve the HTTP status code
// (see the "discovered, not fixed" note in the handoff reply). The
// only reliable way to detect "repo not ready" (409) without
// changing the shared api client is _require_ready_repo()'s fixed
// detail string.
export function isRepoNotReadyError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("not ready yet");
}

export function isGraphNotFoundError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("No call graph found");
}

// ── API calls ──────────────────────────────────────────────────────────────────

async function fetchOverview(repoId: string): Promise<ArchitectureOverview> {
  return api.get<ArchitectureOverview>(`/api/architecture/${repoId}/overview`);
}

async function fetchConfig(repoId: string): Promise<ArchitectureConfigResult> {
  return api.get<ArchitectureConfigResult>(`/api/architecture/${repoId}/config`);
}

async function fetchFolders(repoId: string): Promise<ArchitectureFoldersResult> {
  return api.get<ArchitectureFoldersResult>(`/api/architecture/${repoId}/folders`);
}

async function fetchGraph(
  repoId: string,
  view: ArchitectureGraphView
): Promise<ArchitectureGraphResult> {
  return api.get<ArchitectureGraphResult>(
    `/api/architecture/${repoId}/graph?view=${view}`
  );
}

async function fetchSummary(repoId: string): Promise<ArchitectureSummaryResult> {
  return api.get<ArchitectureSummaryResult>(`/api/architecture/${repoId}/summary`);
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useArchitectureOverview(repoId: string) {
  return useQuery({
    queryKey: ["architecture", "overview", repoId],
    queryFn: () => fetchOverview(repoId),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5, // 5 minutes — matches useHeatmap
    retry: false,
  });
}

export function useArchitectureConfig(repoId: string) {
  return useQuery({
    queryKey: ["architecture", "config", repoId],
    queryFn: () => fetchConfig(repoId),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5,
    retry: false,
  });
}

export function useArchitectureFolders(repoId: string) {
  return useQuery({
    queryKey: ["architecture", "folders", repoId],
    queryFn: () => fetchFolders(repoId),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5,
    retry: false,
  });
}

export function useArchitectureGraph(repoId: string, view: ArchitectureGraphView) {
  return useQuery({
    queryKey: ["architecture", "graph", repoId, view],
    queryFn: () => fetchGraph(repoId, view),
    enabled: !!repoId,
    staleTime: 1000 * 60 * 5,
    retry: false,
  });
}

export function useArchitectureSummary(repoId: string) {
  return useQuery({
    queryKey: ["architecture", "summary", repoId],
    queryFn: () => fetchSummary(repoId),
    enabled: !!repoId,
    // Summary is cached server-side in repos.architecture_summary and
    // only invalidated by re-ingestion — safe to treat as fresh longer
    // than the deterministic panels (mirrors useWalkthrough's reasoning
    // for its own 5-minute staleTime).
    staleTime: 1000 * 60 * 10,
    retry: false,
  });
}