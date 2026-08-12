// components/impact/ImpactSummaryPanel.tsx — RepoMind Impact Analyzer
//
// Milestone 5: renders the AI reasoning headline — ai_summary,
// a Safe-to-Change indicator, and a risk-level badge — above the
// existing dependency graph. Only these three fields are rendered
// here; risk_reasons/affected_files/downstream_call_chain/
// possible_regressions/suggested_test_cases/refactoring_advice are
// typed on ImpactResult but intentionally not rendered until
// Milestone 6/7.
//
// Visual language matches the page's current slate-* palette (not
// neutral-*) to stay consistent with the rest of ImpactAnalyzer.tsx
// as it exists today — the full palette alignment is deferred to
// Milestone 8's page reflow, not done piecemeal here.
//
// risk_level color mapping reuses HeatmapPage's SeverityBadge
// convention exactly: high = red, medium = yellow, low = neutral.

import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
import type { ImpactResult, RiskLevel } from "@/hooks/useImpact";

const RISK_STYLES: Record<RiskLevel, string> = {
  high: "text-red-400 bg-red-950/40 border-red-900/50",
  medium: "text-yellow-400 bg-yellow-950/40 border-yellow-900/50",
  low: "text-slate-400 bg-slate-800 border-slate-700",
};

function RiskBadge({ riskLevel }: { riskLevel: RiskLevel }) {
  return (
    <span
      className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${RISK_STYLES[riskLevel]}`}
    >
      {riskLevel} risk
    </span>
  );
}

function SafeToChangeBadge({ safeToChange }: { safeToChange: boolean | null }) {
  if (safeToChange === null) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border text-slate-400 bg-slate-800 border-slate-700">
        <ShieldQuestion className="h-3 w-3" />
        Safety unknown
      </span>
    );
  }

  if (safeToChange) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border text-teal-300 bg-teal-950/40 border-teal-900/50">
        <ShieldCheck className="h-3 w-3" />
        Safe to change
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border text-red-400 bg-red-950/40 border-red-900/50">
      <ShieldAlert className="h-3 w-3" />
      Review before changing
    </span>
  );
}

export default function ImpactSummaryPanel({ result }: { result: ImpactResult }) {
  const { ai_summary, safe_to_change, risk_level } = result;

  if (ai_summary === null) {
    return (
      <div className="mb-5 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <p className="text-xs text-slate-500">
          AI analysis unavailable for this function. Showing dependency graph only.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-5 rounded-xl border border-slate-800 bg-slate-900/40 p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SafeToChangeBadge safeToChange={safe_to_change} />
        {risk_level !== null && <RiskBadge riskLevel={risk_level} />}
      </div>
      <p className="text-sm leading-relaxed text-slate-300">{ai_summary}</p>
    </div>
  );
}