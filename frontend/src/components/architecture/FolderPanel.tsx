// components/architecture/FolderPanel.tsx — CodeoMentis Architecture Analyzer
//
// Lists top-level folders with file counts and, where the folder
// name matches a known convention, its inferred responsibility.
// Folders with no known convention are still listed with a muted
// label — never hidden — matching _analyze_folders()'s documented
// "still listed, just without a responsibility label" behavior.

import { Folder } from "lucide-react";
import type { FolderEntry } from "@/hooks/useArchitecture";

export default function FolderPanel({ folders }: { folders: FolderEntry[] }) {
  if (folders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
        <Folder className="w-8 h-8 text-neutral-700" />
        <p className="text-sm text-neutral-500">No source folders found</p>
      </div>
    );
  }

  const maxCount = Math.max(...folders.map((f) => f.file_count));

  return (
    <div className="rounded-xl border border-neutral-800 divide-y divide-neutral-800/60 overflow-hidden">
      {folders.map((f) => (
        <div key={f.folder} className="flex items-center gap-4 px-4 py-3 bg-neutral-900">
          <Folder className="w-4 h-4 text-brand-400 shrink-0" />

          <div className="min-w-0 flex-1">
            <p className="font-mono text-sm text-neutral-200 truncate">{f.folder}</p>
            <p
              className={`text-xs mt-0.5 ${
                f.responsibility ? "text-neutral-500" : "text-neutral-700 italic"
              }`}
            >
              {f.responsibility ?? "Unrecognized convention"}
            </p>
          </div>

          <div className="flex flex-col items-end gap-1 shrink-0 w-28">
            <span className="text-xs font-mono text-neutral-400 tabular-nums">
              {f.file_count} file{f.file_count !== 1 ? "s" : ""}
            </span>
            <div className="w-full h-1 rounded-full bg-neutral-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-brand-500"
                style={{ width: `${(f.file_count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}