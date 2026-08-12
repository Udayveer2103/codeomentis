// pages/Walkthrough.tsx — RepoMind Walkthrough Redesign
//
// Onboarding Walkthrough page. Thin shell: layout + UI states only.
// List rendering (including the empty state) is fully delegated to
// ReadingPath. Uses useWalkthrough()'s raw query result directly, matching
// how useHeatmap/useImpact are consumed elsewhere in the app.

import { Link, useParams } from "react-router-dom";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";

import { Alert, AlertDescription } from "@/components/ui/alert";

import { useWalkthrough } from "@/hooks/useWalkthrough";
import { ReadingPath } from "@/components/walkthrough/ReadingPath";
import { WalkthroughSkeleton } from "@/components/walkthrough/WalkthroughSkeleton";

export default function Walkthrough() {
const { repoId } = useParams<{ repoId: string }>();

// Always call hooks unconditionally.
// If repoId is undefined, the hook stays disabled via `enabled: !!repoId`.
const { data, isLoading, error } = useWalkthrough(repoId ?? "");

return (
<div className="min-h-screen bg-neutral-950 flex flex-col dark">
<Header />

<div className="flex flex-1">
<Sidebar />

<main className="flex-1 p-6 max-w-3xl mx-auto w-full">
<div className="mb-6">
<Link
to={repoId ? `/repo/${repoId}` : "/"}
className="text-neutral-400 text-sm hover:text-neutral-200"
>
← Back to repo
</Link>

<h1 className="font-display text-2xl text-neutral-100 mt-2">
Onboarding Walkthrough
</h1>
</div>

{!repoId && (
<Alert variant="destructive">
<AlertDescription>
Invalid repository.
</AlertDescription>
</Alert>
)}

{repoId && isLoading && (
<div className="flex flex-col gap-3">
<p className="text-neutral-500 text-xs mb-1">
Generating your walkthrough... First-time generation may take
10–30 seconds. Once cached, it will load almost instantly.
</p>

<WalkthroughSkeleton />
</div>
)}

{repoId && !isLoading && error && (
<Alert variant="destructive">
<AlertDescription>
{error.message || "Failed to load walkthrough."}
</AlertDescription>
</Alert>
)}

{repoId && !isLoading && !error && data && (
<ReadingPath steps={data.steps} />
)}
</main>
</div>
</div>
);
}