// components/walkthrough/WalkthroughSkeleton.tsx — RepoMind Walkthrough Redesign
//
// Loading placeholder shown while the walkthrough is being fetched or
// generated. Mirrors the shape of real content (a group section with a
// couple of step cards) so the layout doesn't jump once real data
// arrives. Exported for use in Walkthrough.tsx wherever the page renders
// its loading state.

function SkeletonStepCard() {
return (
<div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 sm:p-4 flex gap-3 animate-pulse motion-reduce:animate-none">
<div className="flex-shrink-0 w-5 h-4 bg-neutral-800 rounded" />
<div className="flex-1 min-w-0 flex flex-col gap-2">
<div className="flex items-center justify-between gap-2">
<div className="h-4 bg-neutral-800 rounded w-1/3" />
<div className="h-4 bg-neutral-800 rounded w-16" />
</div>
<div className="h-3 bg-neutral-800 rounded w-full" />
<div className="h-3 bg-neutral-800 rounded w-5/6" />
<div className="h-3 bg-neutral-800 rounded w-1/2 mt-1" />
</div>
</div>
);
}

function SkeletonGroupSection() {
return (
<div className="border border-neutral-800 rounded-xl overflow-hidden">
<div className="px-3 sm:px-4 py-3 bg-neutral-900/60 flex items-center gap-2">
<div className="h-4 bg-neutral-800 rounded w-32 animate-pulse motion-reduce:animate-none" />
<div className="h-3 bg-neutral-800 rounded w-12 animate-pulse motion-reduce:animate-none" />
</div>
<div className="flex flex-col gap-3 p-3 sm:p-4 pt-3">
<SkeletonStepCard />
<SkeletonStepCard />
</div>
</div>
);
}

export function WalkthroughSkeleton() {
return (
<div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
<span className="sr-only">Loading walkthrough…</span>
<SkeletonGroupSection />
<SkeletonGroupSection />
<SkeletonGroupSection />
</div>
);
}