// components/walkthrough/WalkthroughGroupSection.tsx — CodeoMentis Walkthrough Redesign
//
// Renders one group as a visually distinct, collapsible section: a header
// (label + step count) and its ordered step cards. Collapse state for the
// section itself is local — each group's initial state comes from
// collapsedByDefault, but the user can toggle any group open or closed
// independently. Step-details expansion is NOT owned here — it's owned by
// ReadingPath so only one details panel is open across the whole
// walkthrough, and is simply forwarded through to each card.

import { useState } from "react";
import type { WalkthroughGroup } from "@/lib/walkthroughGrouping";
import { getStepKey } from "@/lib/walkthroughGrouping";
import { WalkthroughStepCard } from "./WalkthroughStepCard";

interface WalkthroughGroupSectionProps {
group: WalkthroughGroup;
startIndex: number; // global step index this group starts at, for numbered badges
expandedStepKey: string | null;
onToggleStep: (key: string) => void;
}

export function WalkthroughGroupSection({
group,
startIndex,
expandedStepKey,
onToggleStep,
}: WalkthroughGroupSectionProps) {
const [collapsed, setCollapsed] = useState(group.collapsedByDefault);
const contentId = `group-${group.label
.trim()
.toLowerCase()
.replace(/[^a-z0-9]+/g, "-")}-content`;

return (
<section className="border border-neutral-800 rounded-xl overflow-hidden">
<button
type="button"
onClick={() => setCollapsed((prev) => !prev)}
className="w-full flex items-center justify-between gap-2 px-3 sm:px-4 py-3 bg-neutral-900/60 hover:bg-neutral-900 transition-colors text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500 focus-visible:-outline-offset-2"
aria-expanded={!collapsed}
aria-controls={contentId}
>
<div className="flex items-center gap-2 min-w-0">
<h2 className="font-display text-neutral-100 text-sm truncate">
{group.label}
</h2>
<span className="text-neutral-500 text-xs shrink-0">
{group.steps.length} {group.steps.length === 1 ? "step" : "steps"}
</span>
</div>

<svg
width="16"
height="16"
viewBox="0 0 16 16"
fill="none"
className={`text-neutral-500 shrink-0 transition-transform duration-200 motion-reduce:transition-none ${
collapsed ? "" : "rotate-180"
}`}
>
<path
d="M4 6L8 10L12 6"
stroke="currentColor"
strokeWidth="1.5"
strokeLinecap="round"
strokeLinejoin="round"
/>
</svg>
</button>

<div
id={contentId}
aria-hidden={collapsed}
className={`grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
}`}
>
<div className="overflow-hidden">
<div className="flex flex-col gap-3 p-3 sm:p-4 pt-3">
{group.steps.map((step, i) => {
const key = getStepKey(step);
return (
<WalkthroughStepCard
key={key}
step={step}
index={startIndex + i}
isExpanded={expandedStepKey === key}
onToggleExpand={() => onToggleStep(key)}
/>
);
})}
</div>
</div>
</div>
</section>
);
}