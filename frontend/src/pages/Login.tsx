import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { GitBranch, Eye, EyeOff } from "lucide-react";
import codeoMentisLogo from "@/assets/codeomentis-logo.png";
export default function Login() {
  const { signInWithGitHub, signInWithEmail } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: Location })?.from?.pathname ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signInWithEmail(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGitHub = async () => {
    setError(null);
    try {
      await signInWithGitHub();
      // OAuth redirect happens — no navigate needed
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub sign-in failed");
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex w-1/2 flex-col justify-between p-12 bg-neutral-900 border-r border-neutral-800">
        <div>
          <img
            src={codeoMentisLogo}
            alt="CodeoMentis"
            className="h-10 w-auto object-contain"
          />
        </div>
        <div>
          <p className="font-display text-4xl font-bold text-white leading-tight mb-4">
            The Mind of
            <br />
            <span className="text-brand-400">Your Codebase.</span>
          </p>
          <p className="text-neutral-400 text-sm leading-relaxed max-w-sm">
            Understand unfamiliar repositories faster with architecture
            mapping, impact analysis, technical-debt insights, and
            context-aware code intelligence.
          </p>
        </div>
        <div className="flex gap-6 text-xs text-neutral-600">
          <span>AST-powered</span>
          <span>·</span>
          <span>Graph-based</span>
          <span>·</span>
          <span>Context-aware</span>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fade-in">
          {/* Mobile logo */}
          <div className="flex items-center mb-8 lg:hidden">
            <img
              src={codeoMentisLogo}
              alt="CodeoMentis"
              className="h-9 w-auto object-contain"
            />
          </div>

          <h1 className="text-2xl font-display font-bold text-white mb-1">
            Welcome back
          </h1>
          <p className="text-sm text-neutral-400 mb-1">
            Continue exploring your codebase.
          </p>
          <p className="text-sm text-neutral-400 mb-8">
            Don't have an account?{" "}
            <Link to="/signup" className="text-brand-400 hover:text-brand-300 transition-colors">
              Sign up
            </Link>
          </p>

          {/* GitHub OAuth */}
          <button
            onClick={handleGitHub}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 hover:border-neutral-600 text-white text-sm font-medium transition-all duration-150 mb-6"
          >
            <GitBranch className="w-4 h-4" />
            Continue with GitHub
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-neutral-800" />
            <span className="text-xs text-neutral-600">or</span>
            <div className="flex-1 h-px bg-neutral-800" />
          </div>

          {/* Email form */}
          <form onSubmit={handleEmail} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full px-3 py-2.5 rounded-lg bg-neutral-900 border border-neutral-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30 text-white text-sm placeholder:text-neutral-600 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-400 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full px-3 py-2.5 pr-10 rounded-lg bg-neutral-900 border border-neutral-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30 text-white text-sm placeholder:text-neutral-600 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-300 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-xs text-red-400 bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors duration-150"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}