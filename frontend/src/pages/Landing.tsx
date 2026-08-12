import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import {
  GitFork,
  Network,
  Compass,
  GitMerge,
  Flame,
  BookOpen,
  MessageSquare,
  ArrowRight,
} from "lucide-react";
import repomindLogo from "@/assets/repomind-logo.png";

// ─── Landing header (distinct from the authenticated app Header) ─────────────

function LandingHeader({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <header className="h-14 border-b border-neutral-800 flex items-center justify-between px-4 lg:px-6 shrink-0">
      <Link to="/" className="flex items-center">
        <img src={repomindLogo} alt="RepoMind" className="h-8 w-auto" />
      </Link>

      <Link
        to={isAuthenticated ? "/dashboard" : "/login"}
        className="text-sm font-medium text-neutral-300 hover:text-white transition-colors"
      >
        {isAuthenticated ? "Dashboard" : "Sign in"}
      </Link>
    </header>
  );
}

// ─── How it works step ────────────────────────────────────────────────────────

function Step({
  number,
  icon,
  title,
  description,
}: {
  number: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-neutral-600">{number}</span>
        <div className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center">
          {icon}
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="text-xs text-neutral-500 mt-1 leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
}

// ─── Capability row ───────────────────────────────────────────────────────────

function Capability({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3 py-4 border-b border-neutral-900 last:border-b-0">
      <div className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="text-xs text-neutral-500 mt-0.5 leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Landing() {
  const { isAuthenticated } = useAuth();
  const primaryHref = isAuthenticated ? "/dashboard" : "/login";
  const primaryLabel = isAuthenticated ? "Go to dashboard" : "Get started";

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      <LandingHeader isAuthenticated={isAuthenticated} />

      <main className="flex-1">
        {/* Hero */}
        <section className="max-w-3xl mx-auto px-6 pt-16 sm:pt-24 pb-16 sm:pb-20 text-center">
          <div className="relative mx-auto mb-8 sm:mb-10 w-64 sm:w-80 md:w-96 lg:w-[28rem] aspect-[311/280] overflow-hidden">
  <img
    src={repomindLogo}
    alt="RepoMind: repository structure mapped as a dependency graph"
    className="absolute max-w-none w-[217.7%]"
    style={{ left: "-58.84%", top: "-16.79%" }}
  />
</div>
          <h1 className="text-3xl sm:text-4xl font-display font-bold text-white tracking-tight leading-tight">
            Understand a codebase before you change it.
          </h1>
          <p className="text-neutral-400 text-sm sm:text-base mt-4 max-w-xl mx-auto leading-relaxed">
            RepoMind analyzes a GitHub repository's code, dependencies, and
            structure, then gives you tools to explore how it actually fits
            together.
          </p>
          <div className="mt-8">
            <Link
              to={primaryHref}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-semibold transition-colors"
            >
              {primaryLabel}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

        {/* How it works */}
        <section className="max-w-3xl mx-auto px-6 pb-20">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-6 text-center">
            How it works
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            <Step
              number="01"
              icon={<GitFork className="w-4 h-4 text-brand-400" />}
              title="Connect a repository"
              description="Point RepoMind at a public GitHub repository."
            />
            <Step
              number="02"
              icon={<Network className="w-4 h-4 text-brand-400" />}
              title="RepoMind analyzes it"
              description="It parses the code, builds a dependency graph, and detects the tech stack and architecture."
            />
            <Step
              number="03"
              icon={<Compass className="w-4 h-4 text-brand-400" />}
              title="Explore the results"
              description="Trace impact, review technical debt, read a guided walkthrough, or ask questions directly."
            />
          </div>
        </section>

        {/* Capabilities */}
        <section className="max-w-2xl mx-auto px-6 pb-20">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2 text-center">
            What RepoMind does
          </p>
          <div className="mt-6">
            <Capability
              icon={<GitMerge className="w-4 h-4 text-brand-400" />}
              title="Impact Analysis"
              description="Visualise the blast radius of any function change across the call graph."
            />
            <Capability
              icon={<Flame className="w-4 h-4 text-orange-400" />}
              title="Tech Debt Heatmap"
              description="Score every file by cyclomatic complexity, coupling, TODOs, and function length."
            />
            <Capability
              icon={<BookOpen className="w-4 h-4 text-purple-400" />}
              title="Codebase Walkthrough"
              description="AI-generated reading-order guide to onboard onto any repository fast."
            />
            <Capability
              icon={<Network className="w-4 h-4 text-emerald-400" />}
              title="Architecture Analyzer"
              description="Understand a repo's tech stack, folder structure, config, and dependency graph in minutes."
            />
            <Capability
              icon={<MessageSquare className="w-4 h-4 text-sky-400" />}
              title="Chat with Repo"
              description="Ask questions about the codebase, powered by RAG over code embeddings."
            />
          </div>
        </section>

        {/* Final CTA */}
        <section className="max-w-xl mx-auto px-6 pb-24 text-center">
          <p className="text-sm text-neutral-400">
            Start with a repository you already know.
          </p>
          <div className="mt-5">
            <Link
              to={primaryHref}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-semibold transition-colors"
            >
              {primaryLabel}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-900 py-6 px-6">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <img src={repomindLogo} alt="RepoMind" className="h-5 w-auto opacity-70" />
          <p className="text-xs text-neutral-600">
            © {new Date().getFullYear()} RepoMind
          </p>
        </div>
      </footer>
    </div>
  );
}