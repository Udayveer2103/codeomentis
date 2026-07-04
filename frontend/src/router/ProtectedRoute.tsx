import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useAuth } from "@/hooks/useAuth";

// Shows a spinner while session is loading
function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-950">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-sm text-neutral-500 font-mono">Initializing…</p>
      </div>
    </div>
  );
}

// Redirects unauthenticated users to /login, preserving intended path
export function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  // Initialize auth state
  useAuth();

  const { session, loading } = useAuthStore();
  const location = useLocation();

  if (loading) return <LoadingScreen />;

  if (!session) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// Redirects already-authenticated users to /dashboard
export function PublicRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  // Initialize auth state
  useAuth();

  const { session, loading } = useAuthStore();

  if (loading) return <LoadingScreen />;

  if (session) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}