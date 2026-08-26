export type RepoStatus = "pending" | "indexing" | "ready" | "error";

export interface Repo {
  id: string;
  user_id: string;
  github_url: string;
  owner: string;
  name: string;
  default_branch: string;
  language_stats: Record<string, number>;
  status: RepoStatus;
  error_message?: string;
  file_count: number;
  architecture_pattern?: string;
  architecture_summary?: string;
  created_at: string;
  updated_at: string;
}

export interface FileScore {
  id: string;
  repo_id: string;
  file_path: string;
  language?: string;
  cc_score: number;
  coupling_score: number;
  todo_density: number;
  fn_length_score: number;
  composite_score: number;
  severity: "low" | "medium" | "high";
  line_count: number;
  function_count: number;
  todo_count: number;
}

export interface ChatMessage {
  id: string;
  repo_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export type IngestionStage =
  | "fetching"
  | "parsing"
  | "graphing"
  | "scoring"
  | "embedding"
  | "storing"
  | "ready"
  | "error";

// Structured counters are all optional: a given progress event only
// carries the counters the backend pipeline actually had in scope at
// that stage (see _emit() in app/services/ingestion.py) — an absent
// field means "not reported yet", never a fabricated 0.
export interface IngestionProgress {
  stage: IngestionStage;
  progress: number;
  message: string;
  files_processed?: number;
  total_files?: number;
  functions_extracted?: number;
  chunks_created?: number;
  total_chunks?: number;
  graph_nodes?: number;
  graph_edges?: number;
}

export interface ImpactNode {
  id: string;
  file_path: string;
  function_name: string;
  depth: number;
}

export interface ImpactLink {
  source: string;
  target: string;
}

export interface ImpactResult {
  nodes: ImpactNode[];
  links: ImpactLink[];
}