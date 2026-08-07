// components/architecture/ConfigPanel.tsx — RepoMind Architecture Analyzer
//
// Lists detected configuration files grouped by category, each with
// its deterministically looked-up purpose. The category pill mirrors
// HeatmapPage's SeverityBadge pattern exactly.

import { FileCode2 } from "lucide-react";
import type { ConfigFileEntry } from "@/hooks/useArchitecture";

const CATEGORY_STYLES: Record<string, string> = {
  dependency: "text-sky-400 bg-sky-950/40 border-sky-900/50",
  build: "text-purple-400 bg-purple-950/40 border-purple-900/50",
  styling: "text-pink-400 bg-pink-950/40 border-pink-900/50",
  deployment: "text-amber-400 bg-amber-950/40 border-amber-900/50",
  database: "text-emerald-400 bg-emerald-950/40 border-emerald-900/50",
  other: "text-neutral-400 bg-neutral-800 border-neutral-700",
};

// Mirrors the deterministic category set the backend can return
// (see _CONFIG_PURPOSES / _lookup_config_purpose in
// architecture_service.py) — categories not in this list still
// render, just sorted to the end.
const CATEGORY_ORDER = ["dependency", "build", "styling", "database", "deployment", "other"];

function CategoryBadge({ category }: { category: string }) {
  const style = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.other;
  return (
    <span
      className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${style}`}
    >
      {category}
    </span>
  );
}

export default function ConfigPanel({ files }: { files: ConfigFileEntry[] }) {
  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
        <FileCode2 className="w-8 h-8 text-neutral-700" />
        <p className="text-sm text-neutral-500">No configuration files detected</p>
      </div>
    );
  }

  const grouped = new Map<string, ConfigFileEntry[]>();
  for (const f of files) {
    const list = grouped.get(f.category) ?? [];
    list.push(f);
    grouped.set(f.category, list);
  }

  const categories = [...grouped.keys()].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a);
    const bi = CATEGORY_ORDER.indexOf(b);
    return (ai === -1 ? CATEGORY_ORDER.length : ai) - (bi === -1 ? CATEGORY_ORDER.length : bi);
  });

  return (
    <div className="flex flex-col gap-5">
      {categories.map((category) => {
        const entries = grouped.get(category)!;
        return (
          <div key={category}>
            <div className="flex items-center gap-2 mb-2">
              <CategoryBadge category={category} />
              <span className="text-xs text-neutral-600">
                {entries.length} file{entries.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="rounded-xl border border-neutral-800 divide-y divide-neutral-800/60 overflow-hidden">
              {entries.map((f) => (
                <div
                  key={f.path}
                  className="flex items-center justify-between gap-4 px-4 py-2.5 bg-neutral-900"
                >
                  <span
                    className="font-mono text-xs text-neutral-300 truncate"
                    title={f.path}
                  >
                    {f.path}
                  </span>
                  <span className="text-xs text-neutral-500 text-right shrink-0">
                    {f.purpose}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}