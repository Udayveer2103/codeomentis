// components/architecture/OverviewPanel.tsx — CodeoMentis Architecture Analyzer
//
// Renders the deterministic overview: architecture pattern, file
// counts, language breakdown, and the full tech stack. Pure
// presentational component — ArchitecturePage owns data fetching,
// matching how HeatmapPage's ScoreBar/SeverityBadge only receive
// already-fetched data.

import { Boxes, FileCode, Layers, Settings2 } from "lucide-react";
import type { ArchitectureOverview, TechStackListField } from "@/hooks/useArchitecture";

const TECH_STACK_LABELS: { key: TechStackListField; label: string }[] = [
  { key: "frontend_framework", label: "Frontend" },
  { key: "backend_framework", label: "Backend" },
  { key: "database", label: "Database" },
  { key: "orm", label: "ORM" },
  { key: "authentication", label: "Auth" },
  { key: "styling", label: "Styling" },
  { key: "ai_providers", label: "AI" },
  { key: "deployment", label: "Deployment" },
];

const LANGUAGE_COLORS = [
  "bg-brand-500",
  "bg-sky-500",
  "bg-purple-500",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-neutral-600",
];

function TagRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs text-neutral-500 mb-1.5">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className="text-xs font-medium px-2 py-1 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-200"
          >
            {v}
          </span>
        ))}
      </div>
    </div>
  );
}

function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const entries = Object.entries(languages).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;

  return (
    <div>
      <div className="flex w-full h-2 rounded-full overflow-hidden bg-neutral-800">
        {entries.map(([lang, count], i) => (
          <div
            key={lang}
            className={LANGUAGE_COLORS[i % LANGUAGE_COLORS.length]}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${lang}: ${count}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {entries.map(([lang, count], i) => (
          <span key={lang} className="flex items-center gap-1.5 text-xs text-neutral-500">
            <span
              className={`w-2 h-2 rounded-full ${LANGUAGE_COLORS[i % LANGUAGE_COLORS.length]}`}
            />
            <span className="capitalize">{lang}</span>
            <span className="text-neutral-600">
              {((count / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function OverviewPanel({ overview }: { overview: ArchitectureOverview }) {
  const { tech_stack } = overview;

  const stats = [
    {
      label: "Architecture pattern",
      value: overview.architecture_pattern ?? "Not detected",
      icon: Layers,
    },
    {
      label: "Files",
      value: overview.file_count != null ? overview.file_count.toLocaleString() : "—",
      icon: FileCode,
    },
    {
      label: "Config files",
      value: overview.config_file_count.toLocaleString(),
      icon: Settings2,
    },
    {
      label: "Package manager",
      value: tech_stack?.package_manager ?? "Not detected",
      icon: Boxes,
    },
  ];

  const hasAnyTechStack = TECH_STACK_LABELS.some(
    ({ key }) => (tech_stack?.[key]?.length ?? 0) > 0
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Stat chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(({ label, value, icon: Icon }) => (
          <div
            key={label}
            className="rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-3"
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className="w-3.5 h-3.5 text-brand-400" />
              <p className="text-xs text-neutral-500">{label}</p>
            </div>
            <p className="text-sm font-semibold text-white capitalize truncate" title={value}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Language breakdown */}
      {overview.language_stats && Object.keys(overview.language_stats).length > 0 && (
        <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500 uppercase tracking-widest mb-3">
            Languages
          </p>
          <LanguageBar languages={overview.language_stats} />
        </div>
      )}

      {/* Tech stack */}
      <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4">
        <p className="text-xs text-neutral-500 uppercase tracking-widest mb-4">
          Tech Stack
        </p>
        {!hasAnyTechStack ? (
          <p className="text-sm text-neutral-600">
            No recognized manifests — dependency files may be missing or unrecognized.
            This is expected behavior, not an error.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {TECH_STACK_LABELS.map(({ key, label }) => {
              const values = tech_stack?.[key];
              if (!values || values.length === 0) return null;
              return <TagRow key={key} label={label} values={values} />;
            })}
          </div>
        )}
      </div>
    </div>
  );
}