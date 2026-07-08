// components/walkthrough/ReadingPath.tsx — RepoMind Week 4
//
// Renders the ordered list of walkthrough steps. Owns the empty state and
// the React key choice — uses step_order since it's guaranteed present on
// both cached and freshly-generated responses (id is not, see useWalkthrough.ts).

import type { WalkthroughStep } from "@/hooks/useWalkthrough";
import { WalkthroughStepCard } from "./WalkthroughStepCard";

interface ReadingPathProps {
  steps: WalkthroughStep[];
}

export function ReadingPath({ steps }: ReadingPathProps) {
  if (steps.length === 0) {
    return (
      <div className="text-neutral-500 text-sm text-center py-12">
        No walkthrough steps available for this repo yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {steps.map((step, index) => (
        <WalkthroughStepCard
          key={`${step.step_order}-${step.file_path}`}
          step={step}
          index={index}
        />
      ))}
    </div>
  );
}