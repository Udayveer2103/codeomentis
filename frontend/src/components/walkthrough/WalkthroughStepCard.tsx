// components/walkthrough/WalkthroughStepCard.tsx — RepoMind Walkthrough Redesign
//
// Presentational only: renders a single walkthrough step. Does not fetch
// data. Does not own its own expansion state — the currently expanded
// step is tracked by ReadingPath so only one details panel is open across
// the whole walkthrough at a time; this component just reflects isExpanded
// and reports toggle intent upward via onToggleExpand.
//
// Information hierarchy prioritizes onboarding over graph theory: why the
// step matters leads the card, followed by its description. The numbered
// badge is a minor progress indicator, not a competing focal point — the
// title carries primary visual weight. The file/function metadata line is
// purely informational; expanding into Implementation Details is a
// separate, explicit action.
//
// Accessibility: the toggle is a real <button> (native keyboard support
// for Enter/Space, in the natural Tab order). The details region is
// connected via aria-controls/aria-labelledby, marked aria-hidden while
// collapsed, and pressing Escape while open closes it and returns focus
// to the toggle button.

import { useEffect, useRef } from "react";
import type { WalkthroughRole, WalkthroughStep } from "@/hooks/useWalkthrough";
import { getStepDomId } from "@/lib/walkthroughGrouping";
import { WalkthroughStepDetails } from "./WalkthroughStepDetails";

interface WalkthroughStepCardProps {
step: WalkthroughStep;
index: number; // display position (0-based) — used for the numbered badge only
isExpanded: boolean;
onToggleExpand: () => void;
}

const ROLE_LABELS: Record<WalkthroughRole, string> = {
authentication: "Authentication",
application_shell: "Application Shell",
api: "API",
feature: "Feature",
business_logic: "Business Logic",
utility: "Utility",
};

const ROLE_BADGE_CLASSES: Record<WalkthroughRole, string> = {
authentication: "bg-purple-500/10 text-purple-400 border-purple-500/20",
application_shell: "bg-blue-500/10 text-blue-400 border-blue-500/20",
api: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
feature: "bg-brand-500/10 text-brand-400 border-brand-500/20",
business_logic: "bg-amber-500/10 text-amber-400 border-amber-500/20",
utility: "bg-neutral-500/10 text-neutral-400 border-neutral-500/20",
};

function RoleBadge({ role }: { role: WalkthroughRole }) {
return (
<span
className={`shrink-0 text-[10px] font-mono uppercase tracking-wide px-1.5 py-0.5 rounded border ${ROLE_BADGE_CLASSES[role]}`}
>
{ROLE_LABELS[role]}
</span>
);
}

export function WalkthroughStepCard({
step,
index,
isExpanded,
onToggleExpand,
}: WalkthroughStepCardProps) {
const toggleButtonRef = useRef<HTMLButtonElement>(null);
const domId = getStepDomId(step);
const toggleId = `${domId}-toggle`;
const detailsId = `${domId}-details`;

useEffect(() => {
if (!isExpanded) return;

function handleKeyDown(event: KeyboardEvent) {
if (event.key === "Escape") {
onToggleExpand();
toggleButtonRef.current?.focus();
}
}

document.addEventListener("keydown", handleKeyDown);
return () => document.removeEventListener("keydown", handleKeyDown);
}, [isExpanded, onToggleExpand]);

return (
<div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 sm:p-4 flex gap-3">
<div className="flex-shrink-0 w-5 text-neutral-600 text-xs font-mono pt-0.5 text-right">
{index + 1}
</div>

<div className="flex-1 min-w-0">
<div className="flex items-start justify-between gap-2 flex-wrap">
<h3 className="font-display text-neutral-100 text-sm break-words">
{step.title}
</h3>
<RoleBadge role={step.role} />
</div>

{/* Why this matters — primary content, leads the card */}
<p className="text-neutral-300 text-sm mt-2">{step.reason}</p>

<p className="text-neutral-400 text-sm mt-2">{step.description}</p>

{/* Informational only — file before function, no interaction here */}
<p className="text-neutral-500 text-xs font-mono truncate mt-3">
{step.file_path}
{step.function_name ? ` • ${step.function_name}()` : ""}
</p>

<button
ref={toggleButtonRef}
id={toggleId}
type="button"
onClick={onToggleExpand}
aria-expanded={isExpanded}
aria-controls={detailsId}
className="text-brand-400 hover:text-brand-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500 focus-visible:outline-offset-2 rounded text-xs mt-2 transition-colors"
>
{isExpanded
? "Hide implementation details"
: "View implementation details"}
</button>

<div
id={detailsId}
role="region"
aria-labelledby={toggleId}
aria-hidden={!isExpanded}
className={`grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
}`}
>
<div className="overflow-hidden">
<WalkthroughStepDetails step={step} />
</div>
</div>
</div>
</div>
);
}