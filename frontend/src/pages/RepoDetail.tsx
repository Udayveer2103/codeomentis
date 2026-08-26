import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  GitFork,
  Flame,
  GitMerge,
  MessageSquare,
  BookOpen,
  ArrowLeft,
  Clock,
  FileCode2,
  Layers,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Lock,
  Network,
  Trash2,
} from "lucide-react";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { useRepo, useIngestionProgress } from "@/hooks/useRepo";
import { useDeleteRepo } from "@/hooks/useRepos";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Repo, IngestionProgress, IngestionStage } from "@/types";
// ─── Feature nav cards ────────────────────────────────────────────────────────

interface FeatureCard {
  label: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  ready: boolean;
}

function NavCard({ card }: { card: FeatureCard }) {
  const inner = (
    <div
      className={`relative flex flex-col gap-3 p-5 rounded-xl border transition-all
      ${
        card.ready
          ? "bg-neutral-900 border-neutral-800 hover:border-brand-500/50 hover:bg-neutral-800/60 cursor-pointer group"
          : "bg-neutral-900/50 border-neutral-800/50 opacity-60 cursor-not-allowed"
      }`}
    >
      {!card.ready && (
        <span className="absolute top-3 right-3 flex items-center gap-1 text-[10px] font-medium text-neutral-500 bg-neutral-800 border border-neutral-700 px-2 py-0.5 rounded-full">
          <Lock className="w-2.5 h-2.5" />
          Coming soon
        </span>
      )}

      <div className="w-9 h-9 rounded-lg bg-neutral-800 border border-neutral-700 flex items-center justify-center group-hover:border-brand-500/40 transition-colors">
        {card.icon}
      </div>

      <div>
        <p className="text-sm font-semibold text-white">{card.label}</p>
        <p className="text-xs text-neutral-500 mt-0.5 leading-relaxed">
          {card.description}
        </p>
      </div>

      {card.ready && (
        <p className="text-xs font-medium text-brand-400 mt-auto">
          Open →
        </p>
      )}
    </div>
  );

  return card.ready ? (
    <Link to={card.href}>{inner}</Link>
  ) : (
    <div>{inner}</div>
  );
}

// ─── Ingestion progress panel ──────────────────────────────────────────────────

const STAGE_ORDER: IngestionStage[] = [
  "fetching",
  "parsing",
  "graphing",
  "scoring",
  "embedding",
  "storing",
];

const STAGE_LABELS: Record<IngestionStage, string> = {
  fetching: "Fetching repository",
  parsing: "Parsing source files",
  graphing: "Building call graph",
  scoring: "Scoring complexity",
  embedding: "Generating embeddings",
  storing: "Finalizing",
  ready: "Ready",
  error: "Error",
};

function StageChecklist({ currentStage }: { currentStage: IngestionStage }) {
  const currentIndex = STAGE_ORDER.indexOf(currentStage);

  return (
    <div className="space-y-1.5">
      {STAGE_ORDER.map((stage, i) => {
        const isDone = currentStage === "ready" || currentIndex > i;
        const isActive = currentIndex === i;

        return (
          <div key={stage} className="flex items-center gap-2 text-xs">
            {isDone ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-brand-400 shrink-0" />
            ) : isActive ? (
              <span className="w-3.5 h-3.5 rounded-full bg-brand-500 shrink-0 animate-pulse" />
            ) : (
              <span className="w-3.5 h-3.5 rounded-full border border-neutral-700 shrink-0" />
            )}
            <span
              className={
                isDone
                  ? "text-neutral-400"
                  : isActive
                  ? "text-white font-medium"
                  : "text-neutral-600"
              }
            >
              {STAGE_LABELS[stage]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// Purely a local UI re-render tick for the elapsed-time display — makes
// no network request of any kind, so it is not the polling mechanism
// itself (that's useIngestionProgress in useRepo.ts, which polls via
// TanStack Query's refetchInterval).
function useElapsedSeconds(
  startIso: string | undefined,
  active: boolean
): number | null {
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (!active || !startIso) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [active, startIso]);

  if (!startIso) return null;
  return Math.max(
    0,
    Math.floor((Date.now() - new Date(startIso).getTime()) / 1000)
  );
}

function IngestionProgressPanel({
  repo,
  progress,
}: {
  repo: Repo;
  progress: IngestionProgress | null;
}) {
  const active = repo.status === "indexing" || repo.status === "pending";
  const elapsed = useElapsedSeconds(repo.created_at, active);

  if (repo.status === "error") {
    return (
      <div className="p-5 rounded-xl bg-neutral-900 border border-red-900/50 mb-6">
        <p className="flex items-center gap-2 text-sm font-semibold text-red-400 mb-1">
          <AlertCircle className="w-4 h-4" />
          Ingestion failed
        </p>
        <p className="text-xs text-neutral-400">
          {repo.error_message ||
            progress?.message ||
            "An unknown error occurred."}
        </p>
      </div>
    );
  }

  if (!active) return null;

  const stage = progress?.stage ?? "fetching";
  const pct = progress?.progress ?? 0;

  return (
    <div className="p-5 rounded-xl bg-neutral-900 border border-neutral-800 mb-6">
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-semibold text-white">
          Indexing {repo.owner}/{repo.name}
        </p>
        <span className="text-xs font-mono text-brand-400">{pct}%</span>
      </div>

      <div className="h-1.5 rounded-full bg-neutral-800 overflow-hidden mb-3">
        <div
          className="h-full bg-brand-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className="text-xs text-neutral-400 mb-4">
        {progress?.message ?? "Starting ingestion..."}
      </p>

      {/* Live counters — only fields the backend actually reported for
          this event; never a fabricated 0 for a metric that isn't
          available yet. */}
      {progress && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500 mb-4">
          {progress.total_files != null && (
            <span>
              {progress.files_processed ?? 0} / {progress.total_files} files
            </span>
          )}
          {progress.functions_extracted != null && (
            <span>
              {progress.functions_extracted.toLocaleString()} functions
            </span>
          )}
          {progress.total_chunks != null && (
            <span>
              {progress.chunks_created != null
                ? `${progress.chunks_created.toLocaleString()} / ${progress.total_chunks.toLocaleString()}`
                : progress.total_chunks.toLocaleString()}{" "}
              chunks
            </span>
          )}
          {progress.graph_nodes != null && progress.graph_edges != null && (
            <span>
              {progress.graph_nodes.toLocaleString()} nodes,{" "}
              {progress.graph_edges.toLocaleString()} edges
            </span>
          )}
        </div>
      )}

      <div className="flex items-end justify-between">
        <StageChecklist currentStage={stage} />
        {elapsed != null && (
          <span className="flex items-center gap-1 text-xs text-neutral-600">
            <Clock className="w-3 h-3" />
            Elapsed: {formatElapsed(elapsed)}
          </span>
        )}
      </div>
    </div>
  );
}

// Rich completion stats — only available when this session actually
// polled and observed the final "ready" frame (see useIngestionProgress).
// A repo that was already "ready" before this page load has no
// persisted source for functions/chunks/graph counts (Repo itself only
// stores file_count), so this intentionally does not render in that
// case rather than showing stale or fabricated numbers.
function ReadySummary({ progress }: { progress: IngestionProgress }) {
  return (
    <div className="p-4 rounded-xl bg-brand-500/5 border border-brand-500/20 mb-6 flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="flex items-center gap-2 text-sm font-semibold text-white">
        <CheckCircle2 className="w-4 h-4 text-brand-400" />
        Repository ready
      </span>
      {progress.total_files != null && (
        <span className="text-xs text-neutral-400">
          {progress.total_files.toLocaleString()} files
        </span>
      )}
      {progress.functions_extracted != null && (
        <span className="text-xs text-neutral-400">
          {progress.functions_extracted.toLocaleString()} functions
        </span>
      )}
      {progress.chunks_created != null && (
        <span className="text-xs text-neutral-400">
          {progress.chunks_created.toLocaleString()} embeddings
        </span>
      )}
      {progress.graph_edges != null && (
        <span className="text-xs text-neutral-400">
          {progress.graph_edges.toLocaleString()} call-graph edges
        </span>
      )}
    </div>
  );
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
    ready: {
      label: "Ready",
      className: "text-green-400 bg-green-950/40 border-green-900/50",
      icon: <CheckCircle2 className="w-3 h-3" />,
    },
    indexing: {
      label: "Indexing",
      className: "text-yellow-400 bg-yellow-950/40 border-yellow-900/50",
      icon: <Loader2 className="w-3 h-3 animate-spin" />,
    },
    pending: {
      label: "Pending",
      className: "text-neutral-400 bg-neutral-800 border-neutral-700",
      icon: <Clock className="w-3 h-3" />,
    },
    error: {
      label: "Error",
      className: "text-red-400 bg-red-950/40 border-red-900/50",
      icon: <AlertCircle className="w-3 h-3" />,
    },
  };

  const s = map[status] ?? map.pending;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${s.className}`}
    >
      {s.icon}
      {s.label}
    </span>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`rounded-lg bg-neutral-800 animate-pulse ${className ?? ""}`}
    />
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RepoDetail() {
  const { repoId } = useParams<{ repoId: string }>();
  const { repo, loading, error } = useRepo(repoId ?? "");
  const navigate = useNavigate();
  const deleteRepo = useDeleteRepo();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const { progress } = useIngestionProgress(repoId ?? "", repo?.status);

  const handleConfirmDelete = () => {
    if (!repoId) return;
    deleteRepo.mutate(repoId, {
      onSuccess: () => {
        setShowDeleteDialog(false);
        navigate("/dashboard");
      },
    });
  };

  const featureCards = (id: string): FeatureCard[] => [
    {
      label: "Impact Analysis",
      description:
        "Visualise the blast radius of any function change across the call graph.",
      icon: <GitMerge className="w-4 h-4 text-brand-400" />,
      href: `/repo/${id}/impact`,
      ready: true,
    },
    {
      label: "Tech Debt Heatmap",
      description:
        "Score every file by cyclomatic complexity, coupling, TODOs, and function length.",
      icon: <Flame className="w-4 h-4 text-orange-400" />,
      href: `/repo/${id}/heatmap`,
      ready: true,
    },
    {
      label: "Codebase Walkthrough",
      description:
        "AI-generated reading-order guide to onboard onto any repository fast.",
      icon: <BookOpen className="w-4 h-4 text-purple-400" />,
      href: `/repo/${id}/walkthrough`,
      ready: true,
    },
    {
      label: "Chat with Repo",
      description:
        "Ask questions about the codebase — powered by RAG over code embeddings.",
      icon: <MessageSquare className="w-4 h-4 text-sky-400" />,
      href: `/repo/${id}/chat`,
      ready: true,
    },
    {
      label: "Architecture Analyzer",
      description:
        "Understand a repo's tech stack, folder structure, config, and dependency graph in minutes.",
      icon: <Network className="w-4 h-4 text-emerald-400" />,
      href: `/repo/${id}/architecture`,
      ready: true,
    },
  ];

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto animate-fade-in">

            {/* Back */}
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-300 transition-colors mb-6"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              All repositories
            </Link>

            {/* Error state */}
            {error && (
              <div className="flex items-center gap-2 p-4 rounded-xl bg-red-950/30 border border-red-900/50 text-red-400 text-sm mb-6">
                <AlertCircle className="w-4 h-4 shrink-0" />
                Failed to load repository. It may have been deleted or you may not have access.
              </div>
            )}

            {/* Header card */}
            <div className="p-5 rounded-xl bg-neutral-900 border border-neutral-800 mb-6">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-neutral-800 border border-neutral-700 flex items-center justify-center shrink-0">
                    <GitFork className="w-5 h-5 text-brand-400" />
                  </div>
                  <div className="min-w-0">
                    {loading ? (
                      <>
                        <Skeleton className="h-5 w-48 mb-1.5" />
                        <Skeleton className="h-3.5 w-24" />
                      </>
                    ) : repo ? (
                      <>
                        <h1 className="text-lg font-display font-bold text-white truncate">
                          {repo.owner}/{repo.name}
                        </h1>
                        <p className="text-xs text-neutral-500 mt-0.5">
                          github.com/{repo.owner}/{repo.name}
                        </p>
                      </>
                    ) : null}
                  </div>
                </div>

                {loading ? (
                  <Skeleton className="h-6 w-16 rounded-full" />
                ) : repo ? (
                  <div className="flex items-center gap-3">
                    <StatusBadge status={repo.status} />
                    <button
                      onClick={() => setShowDeleteDialog(true)}
                      className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Remove repository
                    </button>
                  </div>
                ) : null}
              </div>

              {/* Error message */}
              {repo?.error_message && (
                <p className="flex items-center gap-1.5 text-xs text-red-400 mt-3">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {repo.error_message}
                </p>
              )}

              {/* Meta chips */}
              <div className="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-neutral-800">
                {loading ? (
                  <>
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-20" />
                  </>
                ) : repo ? (
                  <>
                    <span className="flex items-center gap-1.5 text-xs text-neutral-400">
                      <FileCode2 className="w-3.5 h-3.5 text-neutral-600" />
                      {repo.file_count > 0
                        ? `${repo.file_count.toLocaleString()} files`
                        : "File count pending"}
                    </span>

                    {repo.architecture_pattern && (
                      <span className="flex items-center gap-1.5 text-xs text-brand-400">
                        <Layers className="w-3.5 h-3.5" />
                        {repo.architecture_pattern}
                      </span>
                    )}

                    <span className="flex items-center gap-1.5 text-xs text-neutral-500">
                      <Clock className="w-3.5 h-3.5 text-neutral-600" />
                      Added {new Date(repo.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </>
                ) : null}
              </div>
            </div>

            {/* Ingestion progress / error state */}
            {repo && <IngestionProgressPanel repo={repo} progress={progress} />}

            {/* One-time rich completion summary — only when this session
                actually watched ingestion finish (see ReadySummary above) */}
            {repo?.status === "ready" && progress?.stage === "ready" && (
              <ReadySummary progress={progress} />
            )}

            {/* Feature cards */}
            <div>
              <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-3">
                Tools
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {loading
                  ? [...Array(4)].map((_, i) => (
                      <Skeleton key={i} className="h-32 rounded-xl" />
                    ))
                  : repoId
                  ? featureCards(repoId).map((card) => (
                      <NavCard key={card.label} card={card} />
                    ))
                  : null}
              </div>
            </div>

          </div>
        </main>
      </div>

      {/* Remove repository confirmation */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove repository</DialogTitle>
            <DialogDescription>
              This removes{" "}
              <span className="text-neutral-200 font-medium">
                {repo ? `${repo.owner}/${repo.name}` : "this repository"}
              </span>{" "}
              and all of its RepoMind data (analysis, walkthroughs, chat
              history) from your account. The GitHub repository itself is
              not affected. This can't be undone.
            </DialogDescription>
          </DialogHeader>

          {deleteRepo.isError && (
            <p className="text-xs text-red-400 bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">
              {deleteRepo.error instanceof Error
                ? deleteRepo.error.message
                : "Failed to remove repository. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleteRepo.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteRepo.isPending}
            >
              {deleteRepo.isPending ? "Removing…" : "Remove repository"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}