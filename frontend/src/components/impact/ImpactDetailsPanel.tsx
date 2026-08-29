// components/impact/ImpactDetailsPanel.tsx — CodeoMentis Impact Analyzer
//
// Milestone 6: renders risk_reasons, possible_regressions,
// affected_files, and downstream_call_chain — the fields explicitly
// deferred at Milestone 5. suggested_test_cases and refactoring_advice
// remain deferred to Milestone 7; page layout/reflow remains deferred
// to Milestone 8 (this panel is placed below the existing graph/stats
// grid, not replacing or reordering it).
//
// Card/header conventions (border, padding, uppercase label row, icon
// sizing) are copied directly from ImpactStats.tsx to keep this panel
// visually native to the page rather than introducing a new style.

import { AlertTriangle, Files, Route, ArrowRight } from "lucide-react";
import type { ImpactResult, DownstreamCallChain } from "@/hooks/useImpact";

interface Props {
  result: ImpactResult;
}

function ChainPath({ chain }: { chain: DownstreamCallChain["chain"] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg bg-slate-800/60 px-3 py-2">
      {chain.map((step, i) => (
        <span key={`${step.file_path}::${step.function_name}::${i}`} className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-slate-300">{step.function_name}</span>
          {i < chain.length - 1 && (
            <ArrowRight className="h-3 w-3 shrink-0 text-slate-600" />
          )}
        </span>
      ))}
    </div>
  );
}

export default function ImpactDetailsPanel({ result }: Props) {
  const { risk_reasons, possible_regressions, affected_files, downstream_call_chain } = result;

  // risk_reasons and possible_regressions fail together under M2's
  // fail-soft contract (both null when the AI layer is unavailable).
  // Guarding on either being null, rather than assuming they always
  // agree, avoids silently hiding a field that's actually present if
  // that contract ever changes.
  const aiRiskUnavailable = risk_reasons === null || possible_regressions === null;

  return (
    <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">

      {/* AI Risk Detail — combined card, spans full width */}
      <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-slate-400">
          <AlertTriangle className="h-3.5 w-3.5" />
          AI Risk Detail
        </div>

        {aiRiskUnavailable ? (
          <p className="text-xs text-slate-500">
            AI analysis unavailable for this function.
          </p>
        ) : (
          <div className="flex flex-col gap-4 text-sm">
            <div>
              <div className="mb-1.5 text-xs font-medium text-slate-400">Risk Reasons</div>
              {risk_reasons.length === 0 ? (
                <p className="text-xs text-slate-500">No specific risk reasons identified.</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {risk_reasons.map((reason, i) => (
                    <li key={i} className="flex items-start gap-2 text-slate-300">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
                      {reason}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <div className="mb-1.5 text-xs font-medium text-slate-400">Possible Regressions</div>
              {possible_regressions.length === 0 ? (
                <p className="text-xs text-slate-500">No specific regressions identified.</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {possible_regressions.map((regression, i) => (
                    <li key={i} className="flex items-start gap-2 text-slate-300">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
                      {regression}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Affected Files */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-slate-400">
          <Files className="h-3.5 w-3.5" />
          Affected Files ({affected_files.length})
        </div>

        {affected_files.length === 0 ? (
          <p className="text-xs text-slate-500">No other files affected.</p>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <ul className="flex flex-col gap-1.5">
              {affected_files.map((path) => (
                <li key={path} className="font-mono text-xs text-slate-300 break-all">
                  {path}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Downstream Call Chain */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-slate-400">
          <Route className="h-3.5 w-3.5" />
          Downstream Call Chain ({downstream_call_chain.length})
        </div>

        {downstream_call_chain.length === 0 ? (
          <p className="text-xs text-slate-500">
            No downstream entry points found within this depth.
          </p>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <div className="flex flex-col gap-2">
              {downstream_call_chain.map((entry, i) => (
                <ChainPath
                  key={`${entry.entry_point.file_path}::${entry.entry_point.function_name}::${i}`}
                  chain={entry.chain}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}