// components/architecture/ArchitectureReport.tsx — CodeoMentis Architecture Analyzer
//
// Composes Overview, Config, Folders, a graph summary, and the AI
// narrative into one scrollable documentation-style page — meant to
// read well as onboarding/portfolio material, not just a live
// dashboard view (see V2 handoff §"locked plan" notes on the report
// page's purpose). Reuses OverviewPanel/ConfigPanel/FolderPanel
// as-is rather than duplicating their rendering.

import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import OverviewPanel from "./OverviewPanel";
import ConfigPanel from "./ConfigPanel";
import FolderPanel from "./FolderPanel";
import type {
  ArchitectureOverview,
  ConfigFileEntry,
  FolderEntry,
  ArchitectureGraphResult,
} from "@/hooks/useArchitecture";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="py-8 border-b border-neutral-800 last:border-b-0">
      <h2 className="font-display text-lg font-semibold text-white mb-4">{title}</h2>
      {children}
    </section>
  );
}

export default function ArchitectureReport({
  overview,
  configFiles,
  folders,
  graph,
  summary,
  summaryLoading,
}: {
  overview: ArchitectureOverview;
  configFiles: ConfigFileEntry[];
  folders: FolderEntry[];
  graph: ArchitectureGraphResult | undefined;
  summary: string | null;
  summaryLoading: boolean;
}) {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="pb-8">
        <h1 className="font-display text-2xl font-bold text-white">{overview.repository}</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Architecture report — generated from deterministic analysis of the repository
        </p>
      </div>

      {/* AI summary leads the report when available */}
      <Section title="Summary">
        {summaryLoading ? (
          <div className="space-y-2">
            <div className="h-3 w-full rounded bg-neutral-800 animate-pulse" />
            <div className="h-3 w-5/6 rounded bg-neutral-800 animate-pulse" />
            <div className="h-3 w-2/3 rounded bg-neutral-800 animate-pulse" />
          </div>
        ) : summary ? (
          <div className="flex gap-3">
            <Sparkles className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
            <p className="text-sm text-neutral-300 leading-relaxed whitespace-pre-line">
              {summary}
            </p>
          </div>
        ) : (
          <p className="text-sm text-neutral-600">
            An AI summary isn't available for this repository yet.
          </p>
        )}
      </Section>

      <Section title="Overview">
        <OverviewPanel overview={overview} />
      </Section>

      <Section title="Folder Organization">
        <FolderPanel folders={folders} />
      </Section>

      <Section title="Configuration">
        <ConfigPanel files={configFiles} />
      </Section>

      <Section title="Architecture Graph">
        {graph ? (
          <p className="text-sm text-neutral-400">
            The module graph has {graph.nodes.length} file
            {graph.nodes.length !== 1 ? "s" : ""} connected by {graph.edges.length}{" "}
            dependenc{graph.edges.length !== 1 ? "ies" : "y"}. Open the{" "}
            <span className="text-brand-400">Graph</span> tab to explore it interactively.
          </p>
        ) : (
          <p className="text-sm text-neutral-600">
            No call graph is available for this repository yet.
          </p>
        )}
      </Section>
    </div>
  );
}