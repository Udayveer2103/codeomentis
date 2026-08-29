// components/walkthrough/ReadingPath.tsx — CodeoMentis Walkthrough Redesign
//
// Owns the empty state, the grouped layout, and the single source of
// truth for which step's Implementation Details panel is open — only one
// panel is open across the entire walkthrough at a time, regardless of
// which group it's in. Buckets steps by group_label via
// groupWalkthroughSteps, then renders one WalkthroughGroupSection per
// group in the order the backend produced.

import { useState } from "react";
import type { WalkthroughStep } from "@/hooks/useWalkthrough";
import { groupWalkthroughSteps } from "@/lib/walkthroughGrouping";
import { WalkthroughGroupSection } from "./WalkthroughGroupSection";

interface ReadingPathProps {
steps: WalkthroughStep[];
}

function EmptyState() {
return (
<div className="flex flex-col items-center gap-3 text-center py-16 px-4">
<svg
width="32"
height="32"
viewBox="0 0 24 24"
fill="none"
className="text-neutral-700"
>
<path
d="M4 5a2 2 0 012-2h9l5 5v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5z"
stroke="currentColor"
strokeWidth="1.5"
strokeLinejoin="round"
/>
<path
d="M14 3v5h5"
stroke="currentColor"
strokeWidth="1.5"
strokeLinejoin="round"
/>
</svg>
<p className="text-neutral-500 text-sm max-w-xs">
No walkthrough steps available for this repo yet.
</p>
</div>
);
}

export function ReadingPath({ steps }: ReadingPathProps) {
const [expandedStepKey, setExpandedStepKey] = useState<string | null>(null);

if (steps.length === 0) {
return <EmptyState />;
}

const groups = groupWalkthroughSteps(steps);

function handleToggleStep(key: string) {
setExpandedStepKey((current) => (current === key ? null : key));
}

let runningIndex = 0;

return (
<div className="flex flex-col gap-4">
{groups.map((group) => {
const startIndex = runningIndex;
runningIndex += group.steps.length;

return (
<WalkthroughGroupSection
key={group.label}
group={group}
startIndex={startIndex}
expandedStepKey={expandedStepKey}
onToggleStep={handleToggleStep}
/>
);
})}
</div>
);
}