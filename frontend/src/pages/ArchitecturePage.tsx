// pages/ArchitecturePage.tsx — CodeoMentis
//
// Repository Architecture Analyzer page. Thin shell: layout, tab
// switching, and the fetch-stage tracker live here; all rendering of
// fetched data is delegated to OverviewPanel / ConfigPanel /
// FolderPanel / ArchitectureGraph / ArchitectureReport — mirrors how
// HeatmapPage owns filter state and Walkthrough delegates to
// ReadingPath.
//
// URL: /repo/:repoId/architecture
//
// Progress: no SSE — the five endpoints reuse already-computed
// ingestion data and are fast, so a client-side per-query stage
// tracker (StageTracker below) is sufficient (locked decision #5 in
// the V2 handoff doc; revisit only if /summary proves to be a real
// bottleneck).

import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Check, Loader2, Network, X } from "lucide-react";

import {
  useArchitectureOverview,
  useArchitectureConfig,
  useArchitectureFolders,
  useArchitectureGraph,
  useArchitectureSummary,
  isRepoNotReadyError,
  isGraphNotFoundError,
  type ArchitectureGraphView,
} from "@/hooks/useArchitecture";

import OverviewPanel from "@/components/architecture/OverviewPanel";
import ConfigPanel from "@/components/architecture/ConfigPanel";
import FolderPanel from "@/components/architecture/FolderPanel";
import ArchitectureGraph from "@/components/architecture/ArchitectureGraph";
import ArchitectureReport from "@/components/architecture/ArchitectureReport";

type Tab = "overview" | "graph" | "report";

// ── Stage tracker ────────────────────────────────────────────────────────────
// Named stages instead of a generic spinner — matches the locked
// decision that progress UI should expose deterministic stage names
// rather than a spinner, even though this reads results rather than
// running the ingestion pipeline itself.

interface Stage {
  label: string;
  status: "loading" | "done" | "error";
}

function StageTracker({ stages }: { stages: Stage[] }) {
  return (
    <div className="flex flex-col gap-2 max-w-sm mx-auto py-16">
      {stages.map((stage) => (
        <div key={stage.label} className="flex items-center gap-3">
          <span className="shrink-0 w-5 h-5 flex items-center justify-center">
            {stage.status === "done" && <Check className="w-4 h-4 text-emerald-400" />}
            {stage.status === "loading" && (
              <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
            )}
            {stage.status === "error" && <X className="w-4 h-4 text-red-400" />}
          </span>
          <span className="text-sm text-neutral-300">{stage.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Tab bar ──────────────────────────────────────────────────────────────────

function TabBar({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "graph", label: "Graph" },
    { id: "report", label: "Report" },
  ];

  return (
    <div className="flex items-center gap-2 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            active === tab.id
              ? "bg-brand-500 text-white"
              : "bg-neutral-800 text-neutral-400 hover:text-white hover:bg-neutral-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function ArchitecturePage() {
  const { repoId } = useParams<{ repoId: string }>();

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [graphView, setGraphView] = useState<ArchitectureGraphView>("module");

  // Always call hooks unconditionally — if repoId is undefined, each
  // hook stays disabled via `enabled: !!repoId` (same convention as
  // Walkthrough's useWalkthrough(repoId ?? "")).
  const overviewQuery = useArchitectureOverview(repoId ?? "");
  const configQuery = useArchitectureConfig(repoId ?? "");
  const foldersQuery = useArchitectureFolders(repoId ?? "");
  const graphQuery = useArchitectureGraph(repoId ?? "", graphView);
  const summaryQuery = useArchitectureSummary(repoId ?? "");

  const notReady =
    isRepoNotReadyError(overviewQuery.error) ||
    isRepoNotReadyError(configQuery.error) ||
    isRepoNotReadyError(foldersQuery.error);

  // Overview, config, and folders are the minimum needed to render
  // anything useful. Graph and summary are allowed to lag behind
  // without blocking the page: graph legitimately 404s on repos
  // ingested before call_graph.json existed, and summary can take
  // 10-30s on first generation (same reasoning Walkthrough uses for
  // its own cached-vs-first-generation copy).
  const coreLoading =
    overviewQuery.isLoading || configQuery.isLoading || foldersQuery.isLoading;
  const coreError = overviewQuery.error ?? configQuery.error ?? foldersQuery.error;

  const stages: Stage[] = [
    {
      label: "Loading overview",
      status: overviewQuery.isLoading ? "loading" : overviewQuery.isError ? "error" : "done",
    },
    {
      label: "Analyzing configuration",
      status: configQuery.isLoading ? "loading" : configQuery.isError ? "error" : "done",
    },
    {
      label: "Mapping folder structure",
      status: foldersQuery.isLoading ? "loading" : foldersQuery.isError ? "error" : "done",
    },
  ];

  const graphNotFound = isGraphNotFoundError(graphQuery.error);

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur">
        <div className="flex h-14 items-center gap-4 px-6 max-w-7xl mx-auto">
          <Link
            to={repoId ? `/repo/${repoId}` : "/"}
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>

          <div className="flex items-center gap-2">
            <Network className="w-4 h-4 text-brand-400" />
            <span className="font-display font-semibold text-white">
              Architecture Analyzer
            </span>
          </div>
        </div>
      </header>

      <main className="flex-1 px-6 py-6 max-w-7xl mx-auto w-full">
        {!repoId && (
          <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
            Invalid repository.
          </div>
        )}

        {repoId && notReady && (
          <div className="rounded-xl border border-yellow-900/50 bg-yellow-950/30 px-4 py-3 text-sm text-yellow-400">
            This repository is still being processed. The Architecture Analyzer becomes
            available once ingestion finishes.
          </div>
        )}

        {repoId && !notReady && coreLoading && <StageTracker stages={stages} />}

        {repoId && !notReady && !coreLoading && coreError && (
          <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
            {coreError instanceof Error
              ? coreError.message
              : "Failed to load architecture data."}
          </div>
        )}

        {repoId && !notReady && !coreLoading && !coreError && overviewQuery.data && (
          <>
            <TabBar active={activeTab} onChange={setActiveTab} />

            {activeTab === "overview" && (
              <div className="flex flex-col gap-8">
                <OverviewPanel overview={overviewQuery.data} />

                <div>
                  <h2 className="text-xs text-neutral-500 uppercase tracking-widest mb-3">
                    Configuration
                  </h2>
                  <ConfigPanel files={configQuery.data?.config_files ?? []} />
                </div>

                <div>
                  <h2 className="text-xs text-neutral-500 uppercase tracking-widest mb-3">
                    Folder Organization
                  </h2>
                  <FolderPanel folders={foldersQuery.data?.folders ?? []} />
                </div>
              </div>
            )}

            {activeTab === "graph" && (
              <>
                {graphQuery.isLoading && (
                  <div className="h-[600px] rounded-xl border border-neutral-800 bg-neutral-900 animate-pulse" />
                )}
                {graphNotFound && (
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-500">
                    No call graph is available for this repository. It may have been
                    ingested before call graph generation was added — re-ingesting will
                    produce one.
                  </div>
                )}
                {graphQuery.isError && !graphNotFound && (
                  <div className="rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
                    {graphQuery.error instanceof Error
                      ? graphQuery.error.message
                      : "Failed to load the architecture graph."}
                  </div>
                )}
                {graphQuery.data && (
                  <ArchitectureGraph
                    data={graphQuery.data}
                    view={graphView}
                    onViewChange={setGraphView}
                  />
                )}
              </>
            )}

            {activeTab === "report" && (
              <ArchitectureReport
                overview={overviewQuery.data}
                configFiles={configQuery.data?.config_files ?? []}
                folders={foldersQuery.data?.folders ?? []}
                graph={graphQuery.data}
                summary={summaryQuery.data?.summary ?? null}
                summaryLoading={summaryQuery.isLoading}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}