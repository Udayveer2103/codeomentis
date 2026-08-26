import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import codeoMentisLogo from "@/assets/codeomentis-logo.png";
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

// ─── Landing header ───────────────────────────────────────────────────────────

function LandingHeader({
  isAuthenticated,
}: {
  isAuthenticated: boolean;
}) {
  return (
    <header className="h-14 border-b border-neutral-800 flex items-center justify-between px-4 lg:px-6 shrink-0">
      <Link to="/" className="flex items-center">
        <img
          src={codeoMentisLogo}
          alt="CodeoMentis"
          className="h-9 w-auto object-contain"
        />
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
        <span className="text-xs font-mono text-neutral-600">
          {number}
        </span>

        <div className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center">
          {icon}
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold text-white">
          {title}
        </p>

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
    <div className="flex items-start gap-3 py-3">
      <div className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center shrink-0">
        {icon}
      </div>

      <div>
        <p className="text-sm font-semibold text-white">
          {title}
        </p>

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
  const primaryLabel = isAuthenticated
    ? "Go to Dashboard"
    : "Get started";

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      <LandingHeader isAuthenticated={isAuthenticated} />

      <main className="flex-1">

        {/* ───────────────────────── HERO ───────────────────────── */}

        <section className="max-w-3xl mx-auto px-6 pt-12 sm:pt-16 pb-10 sm:pb-12 text-center">
          <img
            src={codeoMentisLogo}
            alt="CodeoMentis"
            className="w-72 sm:w-72 h-auto object-contain mx-auto mb-5"
          />

          <p className="text-lg font-medium text-brand-400 tracking-wide mb-5">
            The Mind of Your Codebase.
          </p>

          <h1 className="text-3xl sm:text-4xl font-display font-bold text-white tracking-tight leading-tight">
            Understand your codebase before you change it.
          </h1>

          <p className="text-neutral-400 text-sm sm:text-base mt-4 max-w-xl mx-auto leading-relaxed">
            CodeoMentis maps your repository's architecture, dependencies,
            and code relationships to help you trace changes, uncover
            technical debt, navigate unfamiliar code, and ask questions
            with context.
          </p>

          <div className="mt-6">
            <Link
              to={primaryHref}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-semibold transition-colors"
            >
              {primaryLabel}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

        {/* ───────────────────── HOW IT WORKS ───────────────────── */}

        <section className="max-w-3xl mx-auto px-6 pb-12">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-5 text-center">
            How CodeoMentis works
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-7">
            <Step
              number="01"
              icon={
                <GitFork className="w-4 h-4 text-brand-400" />
              }
              title="Connect your repository"
              description="Connect a public GitHub repository and let CodeoMentis build its understanding."
            />

            <Step
              number="02"
              icon={
                <Network className="w-4 h-4 text-brand-400" />
              }
              title="Build the codebase map"
              description="Parse code, map dependencies, and analyze architecture and relationships."
            />

            <Step
              number="03"
              icon={
                <Compass className="w-4 h-4 text-brand-400" />
              }
              title="Understand and explore"
              description="Trace impact, uncover technical debt, follow guided walkthroughs, or ask questions."
            />
          </div>
        </section>

        {/* ───────────────────── CAPABILITIES ───────────────────── */}

        <section className="max-w-4xl mx-auto px-6 pb-8">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2 text-center">
            What you can understand
          </p>

          {/* Compact, centered capability list */}
          <div className="mt-5 max-w-xl mx-auto">

            <Capability
              icon={
                <GitMerge className="w-4 h-4 text-brand-400" />
              }
              title="Impact Analysis"
              description="Visualize how changes can propagate across the codebase."
            />

            <Capability
              icon={
                <Flame className="w-4 h-4 text-orange-400" />
              }
              title="Tech Debt Heatmap"
              description="Surface complexity, coupling, TODOs, and maintenance hotspots."
            />

            <Capability
              icon={
                <BookOpen className="w-4 h-4 text-purple-400" />
              }
              title="Codebase Walkthrough"
              description="Get an AI-generated reading path for unfamiliar repositories."
            />

            <Capability
              icon={
                <Network className="w-4 h-4 text-emerald-400" />
              }
              title="Architecture Analyzer"
              description="Understand the stack, structure, configuration, and dependencies."
            />

            <Capability
              icon={
                <MessageSquare className="w-4 h-4 text-sky-400" />
              }
              title="Chat with Your Codebase"
              description="Ask questions with context-aware retrieval over your code."
            />

          </div>
        </section>

        {/* ───────────────────── FINAL CTA ───────────────────── */}

        <section className="max-w-xl mx-auto px-6 pb-10 text-center">
          <p className="text-sm text-neutral-400">
            Ready to understand your codebase?
          </p>

          <div className="mt-4">
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

      {/* ───────────────────────── FOOTER ───────────────────────── */}

      <footer className="border-t border-neutral-900 py-6 px-6">
        <div className="w-full flex items-center justify-between">
          
          <div className="flex items-center gap-2">
            <img
              src={codeoMentisLogo}
              alt="CodeoMentis"
              className="h-6 w-auto object-contain"
            />

            <p className="text-xs font-medium text-neutral-500">
              The Mind of Your Codebase.
            </p>
          </div>

          <p className="text-xs text-neutral-600">
            © {new Date().getFullYear()} CodeoMentis
          </p>

        </div>
      </footer>
    </div>
  );
}