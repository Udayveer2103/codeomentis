// components/impact/ImpactForceGraph.tsx
// CodeoMentis Week 3 — Impact Analyzer Graph
//
// Fixed TypeScript-safe D3 implementation
// without changing architecture or logic.

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";

import type { ImpactNode, ImpactLink } from "@/hooks/useImpact";

interface Props {
  nodes: ImpactNode[];
  links: ImpactLink[];
  darkMode?: boolean;
  width?: number;
  height?: number;
  onNodeClick?: (node: ImpactNode) => void;
}

// ── D3 Simulation Type ───────────────────────────────────────────────────────
type SimulationNode = ImpactNode & d3.SimulationNodeDatum;

// ── Depth Colors ─────────────────────────────────────────────────────────────
const DEPTH_COLORS = [
  "#14B8A6",
  "#0EA5E9",
  "#F59E0B",
  "#F97316",
  "#EF4444",
];

function getDepthColor(depth: number): string {
  return DEPTH_COLORS[Math.min(depth, DEPTH_COLORS.length - 1)];
}

export default function ImpactForceGraph({
  nodes,
  links,
  darkMode = true,
  width = 960,
  height = 600,
  onNodeClick,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const drawGraph = useCallback((): (() => void) | void => {
    if (!svgRef.current || nodes.length === 0) return;

    // ── Reset SVG ────────────────────────────────────────────────────────────
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const backgroundColor = darkMode ? "#020617" : "#FFFFFF";
    const textColor = darkMode ? "#E2E8F0" : "#0F172A";
    const linkColor = darkMode ? "#334155" : "#CBD5E1";

    svg.style("background", backgroundColor);

    // ── Root Container ──────────────────────────────────────────────────────
    const container = svg.append("g");

    // ── Zoom ────────────────────────────────────────────────────────────────
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (event) => {
          container.attr("transform", event.transform);
        })
    );

    // ── Nodes ───────────────────────────────────────────────────────────────
    const simulationNodes: SimulationNode[] = nodes.map((node) => ({
      ...node,
      fx: node.depth === 0 ? width / 2 : undefined,
      fy: node.depth === 0 ? height / 2 : undefined,
    }));

    // ── Node Lookup ─────────────────────────────────────────────────────────
    const nodeLookup = new Map(
      simulationNodes.map((node) => [node.id, node])
    );

    // ── Links ───────────────────────────────────────────────────────────────
    const simulationLinks = links.map((link) => ({
      source: nodeLookup.get(link.source) ?? link.source,
      target: nodeLookup.get(link.target) ?? link.target,
    }));

    // ── Force Simulation ────────────────────────────────────────────────────
    const simulation = d3
      .forceSimulation(simulationNodes)
      .force(
        "link",
        d3
          .forceLink(simulationLinks)
          .id((d: any) => d.id)
          .distance(100)
          .strength(0.65)
      )
      .force("charge", d3.forceManyBody().strength(-320))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(26));

    // ── Arrow Marker ────────────────────────────────────────────────────────
    svg
      .append("defs")
      .append("marker")
      .attr("id", "impact-arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 22)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", linkColor);

    // ── Link Lines ──────────────────────────────────────────────────────────
    const linkSelection = container
      .append("g")
      .selectAll("line")
      .data(simulationLinks)
      .join("line")
      .attr("stroke", linkColor)
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.7)
      .attr("marker-end", "url(#impact-arrow)");

    // ── Node Groups ─────────────────────────────────────────────────────────
    const nodeGroup = container
      .append("g")
      .selectAll("g")
      .data(simulationNodes)
      .join("g")
      .attr("cursor", "grab")
      .call(
        d3
          .drag<any, any>()
          .on("start", (event: any, d: any) => {
            if (!event.active) {
              simulation.alphaTarget(0.3).restart();
            }

            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event: any, d: any) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event: any, d: any) => {
            if (!event.active) {
              simulation.alphaTarget(0);
            }

            // Keep root pinned
            if (d.depth !== 0) {
              d.fx = undefined;
              d.fy = undefined;
            }
          })
      );

    // ── Node Circles ────────────────────────────────────────────────────────
    nodeGroup
      .append("circle")
      .attr("r", (d: any) => (d.depth === 0 ? 20 : 13))
      .attr("fill", (d: any) => getDepthColor(d.depth))
      .attr("fill-opacity", 0.92)
      .attr("stroke", "#FFFFFF")
      .attr("stroke-width", (d: any) => (d.depth === 0 ? 2.5 : 1))
      .on("click", (_event: any, d: any) => {
        onNodeClick?.(d);
      })
      .on("mouseenter", (event: any, d: any) => {
        const tooltip = tooltipRef.current;

        if (!tooltip) return;

        tooltip.style.display = "block";
        tooltip.style.left = `${event.pageX + 12}px`;
        tooltip.style.top = `${event.pageY - 24}px`;

        tooltip.innerHTML = `
          <div style="font-weight:600;font-size:12px;">
            ${d.function_name}
          </div>

          <div style="font-size:11px;opacity:0.7;margin-top:4px;">
            ${d.file_path}
          </div>

          <div style="font-size:10px;opacity:0.55;margin-top:6px;">
            depth ${d.depth}
          </div>
        `;
      })
      .on("mouseleave", () => {
        if (tooltipRef.current) {
          tooltipRef.current.style.display = "none";
        }
      });

    // ── Labels ──────────────────────────────────────────────────────────────
    nodeGroup
      .filter((d: any) => d.depth <= 2)
      .append("text")
      .text((d: any) => d.function_name)
      .attr("text-anchor", "middle")
      .attr("y", (d: any) => (d.depth === 0 ? 34 : 24))
      .attr("font-size", (d: any) => (d.depth === 0 ? "12px" : "10px"))
      .attr("fill", textColor)
      .attr("pointer-events", "none");

    // ── Tick Updates ────────────────────────────────────────────────────────
    simulation.on("tick", () => {
      linkSelection
        .attr("x1", (d: any) => d.source.x ?? 0)
        .attr("y1", (d: any) => d.source.y ?? 0)
        .attr("x2", (d: any) => d.target.x ?? 0)
        .attr("y2", (d: any) => d.target.y ?? 0);

      nodeGroup.attr(
        "transform",
        (d: any) => `translate(${d.x ?? 0}, ${d.y ?? 0})`
      );
    });

    // ── Cleanup ─────────────────────────────────────────────────────────────
    return () => {
      simulation.stop();
    };
  }, [nodes, links, darkMode, width, height, onNodeClick]);

  // ── Render Graph ──────────────────────────────────────────────────────────
  useEffect(() => {
    const cleanup = drawGraph();

    return () => {
      if (cleanup) {
        cleanup();
      }
    };
  }, [drawGraph]);

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-slate-800">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full"
      />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="pointer-events-none fixed z-50 hidden rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 text-slate-100 shadow-xl backdrop-blur"
      />

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3 rounded-lg bg-slate-900/80 px-3 py-2 text-xs text-slate-300 backdrop-blur">
        {DEPTH_COLORS.map((color, index) => (
          <div key={index} className="flex items-center gap-1">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: color }}
            />

            <span>d{index}</span>
          </div>
        ))}
      </div>
    </div>
  );
}