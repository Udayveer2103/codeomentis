// components/walkthrough/WalkthroughStepDetails.tsx — RepoMind Walkthrough Redesign
//
// Rendered inside WalkthroughStepCard's animated details region. Presents
// the supporting technical detail behind a step: core identity
// (file/function), then Relationships, then Graph Metrics last — metrics
// are supporting evidence, not information a developer needs to onboard.

import type { WalkthroughRelation, WalkthroughStep } from "@/hooks/useWalkthrough";

interface WalkthroughStepDetailsProps {
step: WalkthroughStep;
}

function RelationColumn({
label,
items,
}: {
label: string;
items: WalkthroughRelation[];
}) {
return (
<div>
<p className="text-neutral-600 mb-1">{label}</p>
{items.length > 0 ? (
<ul className="flex flex-col gap-0.5">
{items.map((rel) => (
<li
key={`${rel.file_path}-${rel.function_name}`}
className="text-neutral-400 font-mono truncate"
title={rel.file_path}
>
{rel.function_name}
</li>
))}
</ul>
) : (
<p className="text-neutral-700">None</p>
)}
</div>
);
}

export function WalkthroughStepDetails({ step }: WalkthroughStepDetailsProps) {
const hasRelationships =
step.called_by !== undefined || step.calls !== undefined;

return (
<div className="mt-3 pt-3 border-t border-neutral-800 flex flex-col gap-4 pb-1">
<div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-xs">
<div className="min-w-0">
<span className="text-neutral-600">File</span>
<p className="text-neutral-300 font-mono mt-0.5 truncate">
{step.file_path}
</p>
</div>
<div className="min-w-0">
<span className="text-neutral-600">Function</span>
<p className="text-neutral-300 font-mono mt-0.5 truncate">
{step.function_name ?? "—"}
</p>
</div>
</div>

{hasRelationships && (
<div>
<h4 className="text-neutral-500 text-xs uppercase tracking-wide mb-1.5">
Relationships
</h4>
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
<RelationColumn label="Called by" items={step.called_by ?? []} />
<RelationColumn label="Calls" items={step.calls ?? []} />
</div>
</div>
)}

<div>
<h4 className="text-neutral-500 text-xs uppercase tracking-wide mb-1.5">
Graph Metrics
</h4>
<div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500 font-mono">
<span>in_degree: {step.in_degree}</span>
<span>out_degree: {step.out_degree}</span>
<span>bfs_level: {step.bfs_level}</span>
</div>
</div>

{/* TODO: add a source-navigation action here ("Open source file" /
"View in editor") once a deep-link target exists. Per the four-layer
spec, it belongs inside Implementation Details, not as its own tier. */}
</div>
);
}