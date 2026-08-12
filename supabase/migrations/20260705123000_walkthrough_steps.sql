-- ============================================================
-- Migration: walkthrough_steps table
-- Feature: Onboarding Walkthrough (Week 4)
--
-- Purpose: caches generated walkthrough steps per repo so the
-- expensive generation pipeline (call-graph analysis + optional
-- LLM description generation) only runs once per repo version.
--
-- Cache invalidation: no new column on `repos` is needed.
-- `source_updated_at` stores the value of `repos.updated_at` that
-- was current when this walkthrough was generated. The API layer
-- compares this against the live `repos.updated_at` (already
-- auto-maintained by the existing `repos_updated_at` trigger) to
-- decide whether to regenerate.
-- ============================================================

CREATE TABLE walkthrough_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id UUID REFERENCES repos(id) ON DELETE CASCADE NOT NULL,
  step_order INT NOT NULL CHECK (step_order >= 0),
  file_path TEXT NOT NULL,
  function_name TEXT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reason TEXT NOT NULL,
  in_degree INT DEFAULT 0,
  out_degree INT DEFAULT 0,
  bfs_level INT DEFAULT 0,
  source_updated_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (repo_id, step_order)
);

ALTER TABLE walkthrough_steps ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own walkthrough_steps" ON walkthrough_steps
FOR ALL USING (
  EXISTS (
    SELECT 1 FROM repos
    WHERE repos.id = walkthrough_steps.repo_id
    AND repos.user_id = auth.uid()
  )
);

-- Composite index matching the cache-lookup query pattern:
-- filter by repo_id -> check source_updated_at for staleness
-- -> order by step_order. Serves the whole GET /api/walkthrough
-- lookup in one index scan.
CREATE INDEX idx_walkthrough_repo_cache
  ON walkthrough_steps (
    repo_id,
    source_updated_at,
    step_order
  );