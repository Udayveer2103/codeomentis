import { NavLink, useParams } from "react-router-dom";
import {
  LayoutDashboard,
  GitFork,
  Flame,
  BookOpen,
  MessageSquare,
  Zap,
} from "lucide-react";
import { clsx } from "clsx";

const dashboardLinks = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
];

function RepoLinks({ repoId }: { repoId: string }) {
  const links = [
    { to: `/repo/${repoId}`, icon: GitFork, label: "Overview", end: true },
    { to: `/repo/${repoId}/impact`, icon: Zap, label: "Impact Analyzer" },
    { to: `/repo/${repoId}/debt`, icon: Flame, label: "Tech Debt" },
    { to: `/repo/${repoId}/walkthrough`, icon: BookOpen, label: "Walkthrough" },
    { to: `/repo/${repoId}/chat`, icon: MessageSquare, label: "Chat" },
  ];

  return (
    <div className="mt-4">
      <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-neutral-500">
        Repository
      </p>
      {links.map(({ to, icon: Icon, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            clsx(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all",
              isActive
                ? "bg-brand-500/10 text-brand-400 font-medium"
                : "text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800"
            )
          }
        >
          <Icon className="w-4 h-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </div>
  );
}

export default function Sidebar() {
  const { repoId } = useParams();

  return (
    <aside className="w-56 shrink-0 border-r border-neutral-800 dark:border-neutral-800 border-neutral-200 bg-white dark:bg-neutral-950 flex flex-col p-2 overflow-y-auto">
      <nav className="flex flex-col gap-0.5">
        {dashboardLinks.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all",
                isActive
                  ? "bg-brand-500/10 text-brand-400 font-medium"
                  : "text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800"
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}

        {repoId && <RepoLinks repoId={repoId} />}
      </nav>
    </aside>
  );
}
