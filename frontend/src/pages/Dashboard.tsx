import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { Plus, GitFork, Clock, AlertCircle } from "lucide-react";
import type { Repo } from "@/types";
import { api } from "@/lib/api";
import { useRepos } from "@/hooks/useRepos";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
      <div className="w-12 h-12 rounded-xl bg-neutral-800 flex items-center justify-center">
        <GitFork className="w-6 h-6 text-neutral-500" />
      </div>
      <div>
        <p className="text-sm font-medium text-neutral-300">No repositories yet</p>
        <p className="text-xs text-neutral-600 mt-1">
          Add a GitHub repo to start analyzing it
        </p>
      </div>
      <button
        onClick={onAdd}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-medium transition-colors"
      >
        <Plus className="w-4 h-4" />
        Add repository
      </button>
    </div>
  );
}

function RepoCard({ repo }: { repo: Repo }) {
  const statusColors: Record<Repo["status"], string> = {
    ready: "text-green-400 bg-green-950/40 border-green-900/50",
    indexing: "text-yellow-400 bg-yellow-950/40 border-yellow-900/50",
    pending: "text-neutral-400 bg-neutral-800 border-neutral-700",
    error: "text-red-400 bg-red-950/40 border-red-900/50",
  };

  const title =
    repo.owner && repo.name
      ? `${repo.owner}/${repo.name}`
      : repo.github_url || "Unknown repository";

  return (
    <Link
      to={`/repo/${repo.id}`}
      className="block p-4 rounded-xl bg-neutral-900 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-800/60 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <GitFork className="w-4 h-4 text-brand-400 shrink-0" />
          <span className="text-sm font-semibold text-white truncate">
            {title}
          </span>
        </div>
        <span
          className={`shrink-0 ml-2 text-[10px] font-medium px-2 py-0.5 rounded-full border ${statusColors[repo.status]}`}
        >
          {repo.status}
        </span>
      </div>

      {repo.status === "error" && (
        <p className="flex items-start gap-1.5 text-xs text-red-400 mb-2">
          <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
          Unable to access repository. It may be private, unreachable, or no
          longer available.
        </p>
      )}

      <div className="flex items-center gap-3 text-xs text-neutral-600">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {new Date(repo.created_at).toLocaleDateString()}
        </span>
        {repo.file_count > 0 && (
          <span>{repo.file_count.toLocaleString()} files</span>
        )}
        {repo.architecture_pattern && (
          <span className="text-brand-500">{repo.architecture_pattern}</span>
        )}
      </div>
    </Link>
  );
}

function AddRepoModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      await api.post("/ingest", {
        github_url: url,
      });

      onClose();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Failed to start ingestion");
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add repository</DialogTitle>
          <DialogDescription>
            Paste a public GitHub URL to start analysis
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            maxLength={200}
            placeholder="https://github.com/owner/repo"
            className="w-full px-3 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30 text-white text-sm placeholder:text-neutral-600 transition-all font-mono"
          />

          {error && (
            <Alert
              variant="destructive"
              className="border-red-900/50 bg-red-950/40 text-red-400"
            >
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg border border-neutral-700 text-neutral-400 hover:text-white hover:border-neutral-600 text-sm font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-semibold transition-colors"
            >
              Start ingestion
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { repos, loading } = useRepos();
  const [showAddModal, setShowAddModal] = useState(false);

  const greeting = user?.user_metadata?.full_name
    ? `Welcome, ${user.user_metadata.full_name.split(" ")[0]}`
    : "Dashboard";

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto animate-fade-in">
            {/* Page header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-2xl font-display font-bold text-white">
                  {greeting}
                </h1>
                <p className="text-sm text-neutral-500 mt-0.5">
                  {repos.length === 0
                    ? "Add your first repository to get started"
                    : `${repos.length} repositor${repos.length === 1 ? "y" : "ies"}`}
                </p>
              </div>
              {repos.length > 0 && (
                <button
                  onClick={() => setShowAddModal(true)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-medium transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add repo
                </button>
              )}
            </div>

            {/* Repo grid */}
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[...Array(3)].map((_, i) => (
                  <div
                    key={i}
                    className="h-24 rounded-xl bg-neutral-900 border border-neutral-800 overflow-hidden relative"
                  >
                    <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-neutral-800/40 to-transparent" />
                  </div>
                ))}
              </div>
            ) : repos.length === 0 ? (
              <EmptyState onAdd={() => setShowAddModal(true)} />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {repos.map((repo) => (
                  <RepoCard key={repo.id} repo={repo} />
                ))}
              </div>
            )}
          </div>
        </main>
      </div>

      {showAddModal && (
        <AddRepoModal onClose={() => setShowAddModal(false)} />
      )}
    </div>
  );
}