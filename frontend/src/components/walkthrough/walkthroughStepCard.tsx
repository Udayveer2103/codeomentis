// components/walkthrough/WalkthroughStepCard.tsx — RepoMind Week 4
//
// Presentational only: renders a single walkthrough step. Does not fetch
// data and does not decide its own React key — that's owned by whichever
// component renders the list (ReadingPath.tsx).

import type { WalkthroughStep } from "@/hooks/useWalkthrough";

interface WalkthroughStepCardProps {
  step: WalkthroughStep;
  index: number; // display position (0-based) — used for the numbered badge only
}

export function WalkthroughStepCard({ step, index }: WalkthroughStepCardProps) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center font-display text-sm">
        {index + 1}
      </div>

      <div className="flex-1 min-w-0">
        <h3 className="font-display text-neutral-100 text-sm">
          {step.title}
        </h3>

        <p className="text-neutral-400 text-xs mt-1 font-mono truncate">
          {step.file_path}
          {step.function_name ? `::${step.function_name}` : ""}
        </p>

        <p className="text-neutral-300 text-sm mt-2">
          {step.description}
        </p>

        <p className="text-neutral-500 text-xs mt-2 italic">
          {step.reason}
        </p>
      </div>
    </div>
  );
}