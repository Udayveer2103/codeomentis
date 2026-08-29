// lib/walkthroughGrouping.ts — CodeoMentis Walkthrough Redesign
//
// Buckets the flat, already-ordered `steps` array into groups by
// group_label. The backend is the single source of truth for group
// membership and order (role → group → per-group ordering happens
// server-side in _compute_reading_order); this function only preserves
// that order by bucketing on first occurrence — it does not re-derive or
// re-sort anything.

import type { WalkthroughStep } from "@/hooks/useWalkthrough";

export interface WalkthroughGroup {
label: string;
steps: WalkthroughStep[];
collapsedByDefault: boolean;
}

// Stable identity for a step, used both as a React list key and as the
// identity tracked for "which step's details panel is open."
export function getStepKey(step: WalkthroughStep): string {
return `${step.step_order}-${step.file_path}`;
}

// DOM-safe id derived from the same identity, for aria-controls /
// aria-labelledby wiring between a toggle button and the region it
// controls. file_path can contain characters that are awkward in an id
// (slashes, brackets from route groups), so this sanitizes rather than
// reusing getStepKey's output directly.
export function getStepDomId(step: WalkthroughStep): string {
return getStepKey(step).replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function groupWalkthroughSteps(
steps: WalkthroughStep[]
): WalkthroughGroup[] {
const order: string[] = [];
const buckets = new Map<string, WalkthroughStep[]>();

for (const step of steps) {
const label = step.group_label;
if (!buckets.has(label)) {
buckets.set(label, []);
order.push(label);
}
buckets.get(label)!.push(step);
}

return order.map((label) => ({
label,
steps: buckets.get(label)!,
// TODO: matching on the literal label string is a v1 shortcut. Once
// the backend can mark a group's default UI state directly (e.g. a
// `collapsed_by_default` flag alongside group_label), drive this from
// that instead of string-matching "utilities".
collapsedByDefault: label.trim().toLowerCase() === "utilities",
}));
}