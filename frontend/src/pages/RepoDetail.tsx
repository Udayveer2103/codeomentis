import { useParams, Link } from "react-router-dom";
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
} from "lucide-react";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { useRepo } from "@/hooks/useRepo";
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
      ready: false,
    },
    {
      label: "Chat with Repo",
      description:
        "Ask questions about the codebase — powered by RAG over code embeddings.",
      icon: <MessageSquare className="w-4 h-4 text-sky-400" />,
      href: `/repo/${id}/chat`,
      ready: false,
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
              to="/"
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
                  <StatusBadge status={repo.status} />
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
    </div>
  );
}