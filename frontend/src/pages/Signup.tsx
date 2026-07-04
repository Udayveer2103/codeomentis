import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { GitBranch, Eye, EyeOff, Terminal } from "lucide-react";

export default function Signup() {
  const { signUp, signInWithGitHub } = useAuth();
  // const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signUp(email, password);
      setSuccess(true); // Supabase sends a confirmation email
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-up failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGitHub = async () => {
    setError(null);
    try {
      await signInWithGitHub();
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub sign-in failed");
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-8">
        <div className="text-center max-w-sm animate-fade-in">
          <div className="w-12 h-12 rounded-full bg-brand-500/10 border border-brand-500/30 flex items-center justify-center mx-auto mb-4">
            <Terminal className="w-6 h-6 text-brand-400" />
          </div>
          <h2 className="text-xl font-display font-bold text-white mb-2">
            Check your email
          </h2>
          <p className="text-sm text-neutral-400">
            We sent a confirmation link to{" "}
            <span className="text-white">{email}</span>. Click it to activate
            your account.
          </p>
          <Link
            to="/login"
            className="mt-6 inline-block text-sm text-brand-400 hover:text-brand-300 transition-colors"
          >
            ← Back to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-8">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="flex items-center gap-2 mb-8">
          <Terminal className="w-5 h-5 text-brand-400" />
          <span className="font-display text-lg font-bold text-white">
            RepoMind
          </span>
        </div>

        <h1 className="text-2xl font-display font-bold text-white mb-1">
          Create account
        </h1>
        <p className="text-sm text-neutral-400 mb-8">
          Already have one?{" "}
          <Link
            to="/login"
            className="text-brand-400 hover:text-brand-300 transition-colors"
          >
            Sign in
          </Link>
        </p>

        <button
          onClick={handleGitHub}
          className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 hover:border-neutral-600 text-white text-sm font-medium transition-all duration-150 mb-6"
        >
          <GitBranch className="w-4 h-4" />
          Continue with GitHub
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px bg-neutral-800" />
          <span className="text-xs text-neutral-600">or</span>
          <div className="flex-1 h-px bg-neutral-800" />
        </div>

        <form onSubmit={handleSignup} className="space-y-4">
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
              Password{" "}
              <span className="text-neutral-600">(min. 8 characters)</span>
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
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
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
