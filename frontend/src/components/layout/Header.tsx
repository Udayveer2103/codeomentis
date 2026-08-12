import { LogOut, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useState, useRef, useEffect } from "react";
import repomindLogo from "@/assets/repomind-logo.png";

export default function Header() {
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? "??";
  const displayName =
    user?.user_metadata?.full_name ??
    user?.user_metadata?.user_name ??
    user?.email ??
    "User";

  return (
    <header className="h-14 border-b border-neutral-800 dark:border-neutral-800 border-neutral-200 bg-white dark:bg-neutral-950 flex items-center justify-between px-4 lg:px-6 shrink-0">
      {/* Logo */}
      <Link to="/" className="flex items-center">
        <img src={repomindLogo} alt="RepoMind" className="h-8 w-auto" />
      </Link>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-all"
          >
            <div className="w-6 h-6 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
              {user?.user_metadata?.avatar_url ? (
                <img
                  src={user.user_metadata.avatar_url}
                  className="w-6 h-6 rounded-full"
                  alt={displayName}
                />
              ) : (
                <span className="text-[10px] font-bold text-brand-400">
                  {initials}
                </span>
              )}
            </div>
            <span className="hidden sm:block text-xs font-medium text-neutral-700 dark:text-neutral-300 max-w-[120px] truncate">
              {displayName}
            </span>
            <ChevronDown className="w-3 h-3 text-neutral-500" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 shadow-xl z-50 animate-fade-in">
              <div className="px-3 py-2 border-b border-neutral-100 dark:border-neutral-800">
                <p className="text-xs text-neutral-500 truncate">{user?.email}</p>
              </div>
              <button
                onClick={signOut}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-b-lg transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}