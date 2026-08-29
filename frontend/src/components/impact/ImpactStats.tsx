// components/impact/ImpactStats.tsx  —  CodeoMentis Week 3
//
// Right-hand panel showing:
//   - blast radius count
//   - breakdown by depth
//   - selected node detail (on node click)

import { useMemo } from "react";
import { AlertTriangle, Layers, GitBranch, FileCode } from "lucide-react";
import type { ImpactNode, ImpactResult } from "@/hooks/useImpact";

interface Props {
  result: ImpactResult;
  selectedNode: ImpactNode | null;
}

const DEPTH_COLORS = ["text-teal-400", "text-sky-400", "text-amber-400", "text-orange-400", "text-red-400"];
const DEPTH_BG     = ["bg-teal-400/10", "bg-sky-400/10", "bg-amber-400/10", "bg-orange-400/10", "bg-red-400/10"];

export default function ImpactStats({ result, selectedNode }: Props) {
  const depthBuckets = useMemo(() => {
    const map: Record<number, number> = {};
    result.nodes.forEach((n) => {
      if (n.depth > 0) map[n.depth] = (map[n.depth] ?? 0) + 1;
    });
    return Object.entries(map)
      .map(([d, count]) => ({ depth: Number(d), count }))
      .sort((a, b) => a.depth - b.depth);
  }, [result]);

  const severity =
    result.total_impacted >= 20
      ? { label: "High", color: "text-red-400", bg: "bg-red-400/10" }
      : result.total_impacted >= 8
      ? { label: "Medium", color: "text-amber-400", bg: "bg-amber-400/10" }
      : { label: "Low", color: "text-teal-400", bg: "bg-teal-400/10" };

  return (
    <div className="flex flex-col gap-4 text-sm">

      {/* Blast radius summary */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 mb-3 text-slate-400 text-xs uppercase tracking-widest">
          <AlertTriangle className="h-3.5 w-3.5" />
          Blast Radius
        </div>
        <div className="text-4xl font-bold text-slate-100 tabular-nums">
          {result.total_impacted}
        </div>
        <div className="text-slate-500 text-xs mt-0.5">functions affected</div>
        <div className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${severity.bg} ${severity.color}`}>
          {severity.label} impact
        </div>
      </div>

      {/* Depth breakdown */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 mb-3 text-slate-400 text-xs uppercase tracking-widest">
          <Layers className="h-3.5 w-3.5" />
          By Depth
        </div>
        <div className="flex flex-col gap-2">
          {depthBuckets.map(({ depth, count }) => (
            <div key={depth} className="flex items-center gap-2">
              <span className={`w-14 text-xs font-mono ${DEPTH_COLORS[Math.min(depth, 4)]}`}>
                depth {depth}
              </span>
              <div className="flex-1 h-1.5 rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full ${DEPTH_BG[Math.min(depth, 4)]
                    .replace("/10", "/80")}`}
                  style={{ width: `${Math.min(100, (count / result.total_impacted) * 100)}%` }}
                />
              </div>
              <span className="w-6 text-right text-xs text-slate-400">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Graph stats */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 mb-3 text-slate-400 text-xs uppercase tracking-widest">
          <GitBranch className="h-3.5 w-3.5" />
          Graph
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-slate-400">Total nodes</div>
            <div className="text-slate-200 font-mono font-medium">
              {result.graph_stats.total_nodes.toLocaleString()}
            </div>
          </div>
          <div>
            <div className="text-slate-400">Total edges</div>
            <div className="text-slate-200 font-mono font-medium">
              {result.graph_stats.total_edges.toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Selected node detail */}
      {selectedNode && (
        <div className="rounded-xl border border-teal-800/50 bg-teal-950/30 p-4">
          <div className="flex items-center gap-2 mb-3 text-teal-400 text-xs uppercase tracking-widest">
            <FileCode className="h-3.5 w-3.5" />
            Selected Node
          </div>
          <div className="font-mono text-sm font-semibold text-teal-300 break-all">
            {selectedNode.function_name}
          </div>
          <div className="mt-1 text-xs text-slate-400 break-all">
            {selectedNode.file_path}
          </div>
          <div className="mt-2 text-xs text-slate-500">
            depth {selectedNode.depth}
          </div>
        </div>
      )}
    </div>
  );
}