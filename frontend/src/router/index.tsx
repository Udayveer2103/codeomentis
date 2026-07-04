import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "./ProtectedRoute";

import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Dashboard from "@/pages/Dashboard";
import AuthCallback from "@/pages/AuthCallback";

import RepoDetail from "@/pages/RepoDetail";
import ImpactAnalyzer from "@/pages/ImpactAnalyzer";
import HeatmapPage from "@/pages/HeatmapPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/dashboard" replace />,
  },

  {
    path: "/login",
    element: (
      <PublicRoute>
        <Login />
      </PublicRoute>
    ),
  },

  {
    path: "/signup",
    element: (
      <PublicRoute>
        <Signup />
      </PublicRoute>
    ),
  },

  {
    path: "/auth/callback",
    element: <AuthCallback />,
  },

  {
    path: "/dashboard",
    element: (
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    ),
  },

  // ───────────────── Repo Detail ─────────────────

  {
    path: "/repo/:repoId",
    element: (
      <ProtectedRoute>
        <RepoDetail />
      </ProtectedRoute>
    ),
  },

  // ───────────────── Impact ─────────────────

  {
    path: "/repo/:repoId/impact",
    element: (
      <ProtectedRoute>
        <ImpactAnalyzer />
      </ProtectedRoute>
    ),
  },

  // ───────────────── Heatmap ─────────────────
  // Change "debt" to "heatmap" ONLY if RepoDetail links there.

  {
    path: "/repo/:repoId/debt",
    element: (
      <ProtectedRoute>
        <HeatmapPage />
      </ProtectedRoute>
    ),
  },

  // ───────────────── Walkthrough ─────────────────

  {
    path: "/repo/:repoId/walkthrough",
    element: (
      <ProtectedRoute>
        <div className="p-8 text-white">
          Walkthrough — Coming Soon
        </div>
      </ProtectedRoute>
    ),
  },

  // ───────────────── Chat ─────────────────

  {
    path: "/repo/:repoId/chat",
    element: (
      <ProtectedRoute>
        <div className="p-8 text-white">
          Chat — Coming Soon
        </div>
      </ProtectedRoute>
    ),
  },
]);

export default function AppRouter() {
  return <RouterProvider router={router} />;
}