// components/impact/CrossFeatureLinks.tsx — RepoMind Impact Analyzer
//
// Milestone 8: repo-scoped navigation to the other RepoMind features.
// Routes confirmed directly from the app's router config — no query
// params or file/function deep-linking invented, since no inspected
// page (Heatmap, the only one seen in full) shows support for that.
//
// Icons are a reasonable choice, not a confirmed match to each
// target page's own header icon — Flame is confirmed to match
// HeatmapPage.tsx's actual header icon (seen directly); Walkthrough/
// Architecture/Chat icons are my best guess, since those pages'
// source hasn't been inspected in this session.

import { Link } from "react-router-dom";
import { Compass, Flame, Network, MessageSquare, ArrowUpRight } from "lucide-react";

interface Props {
  repoId: string;
}

const LINKS = (repoId: string) => [
  {
    label: "Walkthrough",
    href: `/repo/${repoId}/walkthrough`,
    icon: Compass,
  },
  {
    label: "Heatmap",
    href: `/repo/${repoId}/heatmap`,
    icon: Flame,
  },
  {
    label: "Architecture",
    href: `/repo/${repoId}/architecture`,
    icon: Network,
  },
  {
    label: "Chat",
    href: `/repo/${repoId}/chat`,
    icon: MessageSquare,
  },
];

export default function CrossFeatureLinks({ repoId }: Props) {
  return (
    <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 text-xs uppercase tracking-widest text-slate-400">
        Explore this repo further
      </div>
      <div className="flex flex-wrap gap-2">
        {LINKS(repoId).map(({ label, href, icon: Icon }) => (
          <Link
            key={href}
            to={href}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-700 hover:text-slate-100"
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
            <ArrowUpRight className="h-3 w-3 text-slate-500" />
          </Link>
        ))}
      </div>
    </div>
  );
}