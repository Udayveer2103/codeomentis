-- ============================================================
-- Migration: replace_walkthrough_steps() RPC
-- Feature: Onboarding Walkthrough (Week 4)
--
-- Purpose: atomic delete+insert of a repo's walkthrough_steps rows
-- in a single transaction.
-- ============================================================

CREATE OR REPLACE FUNCTION replace_walkthrough_steps(
  p_repo_id UUID,
  p_rows JSONB
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  DELETE FROM walkthrough_steps WHERE repo_id = p_repo_id;

  INSERT INTO walkthrough_steps (
    repo_id,
    step_order,
    file_path,
    function_name,
    title,
    description,
    reason,
    in_degree,
    out_degree,
    bfs_level,
    source_updated_at
  )
  SELECT
    p_repo_id,
    (r->>'step_order')::INT,
    r->>'file_path',
    r->>'function_name',
    r->>'title',
    r->>'description',
    r->>'reason',
    COALESCE((r->>'in_degree')::INT, 0),
    COALESCE((r->>'out_degree')::INT, 0),
    COALESCE((r->>'bfs_level')::INT, 0),
    (r->>'source_updated_at')::TIMESTAMPTZ
  FROM jsonb_array_elements(p_rows) AS r;
END;
$$;