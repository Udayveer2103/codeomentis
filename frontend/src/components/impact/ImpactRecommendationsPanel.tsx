// components/impact/ImpactRecommendationsPanel.tsx — CodeoMentis Impact Analyzer
//
// Milestone 7: renders suggested_test_cases and refactoring_advice —
// the last two AI-generated fields not yet in the UI. Placed as its
// own full-width card below ImpactDetailsPanel (Milestone 6); no page
// reflow (Milestone 8) and no interactive checklist state — this is a
// static, informational list, not a functional to-do list.
//
// Card/header conventions copied from ImpactStats.tsx / ImpactSummaryPanel.tsx
// / ImpactDetailsPanel.tsx, consistent with Milestones 5 and 6.
//
// Null handling: the combined "AI analysis unavailable" message only
// renders when BOTH fields are null (a true, symmetric AI failure).
// If only one field is null while the other has data, that would
// incorrectly claim total unavailability — instead, the null field
// falls back to its own "nothing to suggest" wording while the
// populated field still renders normally. This defensively avoids
// ever hiding a field that the AI actually returned.

import { Lightbulb, CheckSquare } from "lucide-react";
import type { ImpactResult } from "@/hooks/useImpact";

interface Props {
  result: ImpactResult;
}

export default function ImpactRecommendationsPanel({ result }: Props) {
  const { suggested_test_cases, refactoring_advice } = result;

  const bothUnavailable = suggested_test_cases === null && refactoring_advice === null;

  const testCases = suggested_test_cases ?? [];
  const adviceText = (refactoring_advice ?? "").trim();

  return (
    <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-slate-400">
        <Lightbulb className="h-3.5 w-3.5" />
        Recommendations
      </div>

      {bothUnavailable ? (
        <p className="text-xs text-slate-500">
          AI analysis unavailable for this function.
        </p>
      ) : (
        <div className="flex flex-col gap-4 text-sm">
          <div>
            <div className="mb-1.5 text-xs font-medium text-slate-400">
              Suggested Test Cases
            </div>
            {testCases.length === 0 ? (
              <p className="text-xs text-slate-500">No specific test cases suggested.</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {testCases.map((testCase, i) => (
                  <li key={i} className="flex items-start gap-2 text-slate-300">
                    <CheckSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
                    {testCase}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="mb-1.5 text-xs font-medium text-slate-400">
              Refactoring Advice
            </div>
            {adviceText === "" ? (
              <p className="text-xs text-slate-500">No specific refactoring advice.</p>
            ) : (
              <p className="text-sm leading-relaxed text-slate-300">{adviceText}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}