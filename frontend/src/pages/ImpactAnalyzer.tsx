// pages/ImpactAnalyzer.tsx — RepoMind Week 3
//
// Full Impact Analyzer page.
// URL: /repo/:repoId/impact
//
// Layout:
// Top bar — repo name + depth slider
// Main area — FunctionSearch | AI Summary | Details | Recommendations |
//             Cross-Feature Links | collapsible Dependency Graph (ForceGraph + Stats)
//
// Reads repoId from React Router params.
//
// Milestone 5: added ImpactSummaryPanel above the graph/stats grid.
// Milestone 6: added ImpactDetailsPanel below the graph/stats grid.
// Milestone 7: added ImpactRecommendationsPanel below ImpactDetailsPanel.
// Milestone 8: reordered the page so AI content (Summary → Details →
// Recommendations) leads, added CrossFeatureLinks, and wrapped the
// existing graph/stats grid in a collapsible "Dependency Graph" section
// (collapsed by default, CSS grid-template-rows 0fr/1fr transition —
// same technique already used elsewhere in RepoMind, no new dependency).
// ImpactForceGraph and ImpactStats remain always-mounted and completely
// untouched internally — collapsing only changes their container's
// visibility, never their props, so their D3 lifecycle is unaffected
// by the toggle. FunctionSearch, ImpactSummaryPanel, ImpactDetailsPanel,
// ImpactRecommendationsPanel, and existing 404/500 error handling are
// all unchanged.

import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Zap, SlidersHorizontal, ChevronDown, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import FunctionSearch from "../components/impact/FunctionSearch";
import ImpactForceGraph from "../components/impact/ImpactForceGraph";
import ImpactStats from "../components/impact/ImpactStats";
import ImpactSummaryPanel from "../components/impact/ImpactSummaryPanel";
import ImpactDetailsPanel from "../components/impact/ImpactDetailsPanel";
import ImpactRecommendationsPanel from "../components/impact/ImpactRecommendationsPanel";
import CrossFeatureLinks from "../components/impact/CrossFeatureLinks";
import { useImpactAnalysis } from "@/hooks/useImpact";
import type { ImpactNode } from "@/hooks/useImpact";

export default function ImpactAnalyzer() {
  const { repoId } = useParams<{ repoId: string }>();
  const [selectedFunction, setSelectedFunction] = useState<string | null>(null);
  const [maxDepth, setMaxDepth] = useState(4);
  const [selectedNode, setSelectedNode] = useState<ImpactNode | null>(null);
  const [graphExpanded, setGraphExpanded] = useState(false);

  const {
    data: result,
    isLoading,
    isError,
    error,
  } = useImpactAnalysis(repoId!, selectedFunction, maxDepth);

  // Parse error suggestions from API (404 with suggestions array)
  const errorDetail = (error as any)?.response?.data?.detail;
  const suggestions: string[] = errorDetail?.suggestions ?? [];
  const errorMessage: string =
    typeof errorDetail === "string"
      ? errorDetail
      : errorDetail?.message ?? "Something went wrong";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">

      {/* ── Top bar ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-4 px-6">
          <Link to={`/repo/${repoId}`}>
            <Button variant="ghost" size="sm" className="gap-1.5 text-slate-400 hover:text-slate-100">
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
          </Link>

          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-teal-400" />
            <span className="font-semibold text-slate-100">Impact Analyzer</span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <SlidersHorizontal className="h-4 w-4 text-slate-500" />
            <span className="text-xs text-slate-400 w-16">Max depth {maxDepth}</span>
            <Slider
              min={1}
              max={8}
              step={1}
              value={[maxDepth]}
              onValueChange={([v]) => setMaxDepth(v)}
              className="w-28"
            />
          </div>
        </div>
      </header>

      {/* ── Body ─────────────────────────────────────────────────────────── */}
      <main className="mx-auto max-w-[1600px] px-6 py-6">

        {/* Function search bar */}
        <div className="mb-5 max-w-2xl">
          <label className="mb-1.5 block text-xs text-slate-400 uppercase tracking-widest">
            Select function to analyse
          </label>
          <FunctionSearch
            repoId={repoId!}
            value={selectedFunction}
            onChange={(v: string) => {
              setSelectedFunction(v);
              setSelectedNode(null);
            }}

          />
        </div>

        {/* Empty state */}
        {!selectedFunction && (
          <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-slate-800 py-28 text-center">
            <Zap className="h-10 w-10 text-slate-700" />
            <p className="text-slate-500 text-sm">
              Pick a function above to see its blast radius
            </p>
            <p className="text-slate-600 text-xs max-w-xs">
                            CodeoMentis will trace every caller up to depth {maxDepth} using the
              call graph built during ingestion.
            </p>
          </div>
        )}

        {/* Loading */}
        {selectedFunction && isLoading && (
          <div>
            <Skeleton className="mb-5 h-24 rounded-xl bg-slate-800" />
            <div className="grid grid-cols-[1fr_260px] gap-4">
              <Skeleton className="h-[580px] rounded-xl bg-slate-800" />
              <div className="flex flex-col gap-4">
                <Skeleton className="h-36 rounded-xl bg-slate-800" />
                <Skeleton className="h-36 rounded-xl bg-slate-800" />
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {selectedFunction && isError && (
          <Alert className="border-red-800 bg-red-950/40 text-red-300 max-w-xl">
            <AlertDescription>
              <p>{errorMessage}</p>
              {suggestions.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-slate-400 mb-2">Did you mean one of these?</p>
                  <div className="flex flex-wrap gap-1.5">
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        onClick={() => setSelectedFunction(s)}
                        className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-teal-300 hover:bg-slate-700"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Result */}
        {result && !isLoading && (
          <>
            <ImpactSummaryPanel result={result} />

            <ImpactDetailsPanel result={result} />

            <ImpactRecommendationsPanel result={result} />

            <CrossFeatureLinks repoId={repoId!} />

            {/* ── Collapsible Dependency Graph section ─────────────────────
                ForceGraph + Stats stay always-mounted; only this wrapper's
                grid-template-rows toggles between 0fr (collapsed) and 1fr
                (expanded). ImpactForceGraph/ImpactStats props never change
                as a result of this toggle, so their D3 simulation and
                selected-node state are never reset by collapsing/expanding. */}
            <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/60">
              <button
                type="button"
                onClick={() => setGraphExpanded((v) => !v)}
                className="flex w-full items-center gap-2 px-4 py-3 text-left"
              >
                <GitBranch className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-xs uppercase tracking-widest text-slate-400">
                  Dependency Graph
                </span>
                <span className="text-xs text-slate-600">
                  {result.graph_stats.total_nodes.toLocaleString()} nodes ·{" "}
                  {result.graph_stats.total_edges.toLocaleString()} edges (full repository graph)
                </span>
                <ChevronDown
                  className={`ml-auto h-4 w-4 text-slate-500 transition-transform ${
                    graphExpanded ? "rotate-180" : ""
                  }`}
                />
              </button>

              <div
                className="grid transition-[grid-template-rows] duration-300 ease-in-out"
                style={{ gridTemplateRows: graphExpanded ? "1fr" : "0fr" }}
              >
                <div className="overflow-hidden">
                  <div className="grid grid-cols-[1fr_260px] gap-5 items-start p-4 pt-0">
                    {/* Graph */}
                    <div>
                      {result.nodes.length <= 1 ? (
                        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-slate-800 py-28 text-center">
                          <p className="text-slate-400 text-sm">No callers found</p>
                          <p className="text-slate-600 text-xs">
                            This function is not called by anything in the codebase (or within depth {maxDepth}).
                          </p>
                        </div>
                      ) : (
                        <ImpactForceGraph
                          nodes={result.nodes}
                          links={result.links}
                          darkMode={true}
                          height={580}
                          onNodeClick={setSelectedNode}
                        />
                      )}
                    </div>

                    {/* Stats panel */}
                    <ImpactStats result={result} selectedNode={selectedNode} />
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}