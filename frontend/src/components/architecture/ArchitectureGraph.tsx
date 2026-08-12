// components/architecture/ArchitectureGraph.tsx — RepoMind Architecture Analyzer
//
// Renders the architecture graph via React Flow, auto-laid-out with
// Dagre (locked decision — see V2 handoff §3.4). Presentational:
// ArchitecturePage owns the view state and data fetching, and passes
// the fetched result + view + setter down — mirrors how HeatmapPage
// owns `filters` and passes derived data to ColHeader/FileDrawer.
//
// New dependencies this component introduces to the project (not
// used elsewhere — ImpactAnalyzer uses D3 v7 force-directed instead):
//   npm install reactflow dagre
//   npm install -D @types/dagre

import { useMemo } from "react";
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";
import dagre from "dagre";
import { Waypoints } from "lucide-react";
import type {
  ArchitectureGraphResult,
  ArchitectureGraphView,
  FunctionNodeData,
  ModuleNodeData,
} from "@/hooks/useArchitecture";

const NODE_WIDTH = 200;
const NODE_HEIGHT = 56;

function layoutWithDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 90 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });
}

function toFlowNode(
  raw: ArchitectureGraphResult["nodes"][number],
  view: ArchitectureGraphView
): Node {
  const isModule = view === "module";
  const data = raw.data as ModuleNodeData & Partial<FunctionNodeData>;

  return {
    id: raw.id,
    data: {
      label: (
        <div className="text-left">
          <p
            className="font-mono text-[11px] text-white truncate max-w-[170px]"
            title={data.label}
          >
            {data.label}
          </p>
          <p className="text-[10px] text-neutral-500 mt-0.5 truncate max-w-[170px]">
            {isModule
              ? `${data.function_count} function${data.function_count !== 1 ? "s" : ""}`
              : data.file_path ?? ""}
          </p>
        </div>
      ),
    },
    position: { x: 0, y: 0 },
    style: {
      width: NODE_WIDTH,
      background: "#171717", // neutral-900
      border: "1px solid #404040", // neutral-700
      borderRadius: 10,
      padding: "8px 12px",
    },
  };
}

export default function ArchitectureGraph({
  data,
  view,
  onViewChange,
}: {
  data: ArchitectureGraphResult;
  view: ArchitectureGraphView;
  onViewChange: (view: ArchitectureGraphView) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const flowNodes = data.nodes.map((n) => toFlowNode(n, view));
    const flowEdges: Edge[] = data.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      style: { stroke: "#525252" }, // neutral-600
    }));

    return {
      nodes: layoutWithDagre(flowNodes, flowEdges),
      edges: flowEdges,
    };
  }, [data, view]);

  return (
    <div className="flex flex-col gap-4">
      {/* View switcher */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-neutral-600 mr-1">View:</span>
        {(["module", "calls"] as ArchitectureGraphView[]).map((v) => (
          <button
            key={v}
            onClick={() => onViewChange(v)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              view === v
                ? "bg-brand-500 text-white"
                : "bg-neutral-800 text-neutral-400 hover:text-white hover:bg-neutral-700"
            }`}
          >
            {v === "module" ? "Module graph" : "Call graph"}
          </button>
        ))}
        <span className="ml-auto text-xs text-neutral-600">
          {data.nodes.length} node{data.nodes.length !== 1 ? "s" : ""} ·{" "}
          {data.edges.length} edge{data.edges.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Graph canvas */}
      {data.nodes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center gap-3 rounded-xl border border-neutral-800">
          <Waypoints className="w-8 h-8 text-neutral-700" />
          <p className="text-sm text-neutral-500">No graph data for this view</p>
        </div>
      ) : (
        <div className="h-[600px] rounded-xl border border-neutral-800 overflow-hidden bg-neutral-950">
          <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
            <Background color="#262626" gap={20} />
            <Controls className="!bg-neutral-900 !border-neutral-800 [&>button]:!bg-neutral-900 [&>button]:!border-neutral-800 [&>button]:!text-neutral-400" />
            <MiniMap
              maskColor="rgba(10,10,10,0.6)"
              nodeColor="#404040"
              className="!bg-neutral-900 !border !border-neutral-800"
            />
          </ReactFlow>
        </div>
      )}
    </div>
  );
}