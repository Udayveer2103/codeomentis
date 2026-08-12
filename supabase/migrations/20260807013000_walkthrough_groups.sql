-- ============================================================
-- Migration: add role + group_label to walkthrough_steps
-- Feature: Onboarding Walkthrough redesign (v2 spec)
--
-- Additive only. Both columns nullable — existing cached rows
-- remain valid until their next natural regeneration (triggered
-- by the existing source_updated_at staleness check; no backfill
-- script needed).
--
-- Deliberately NOT adding called_by / calls columns: per the
-- approved simplification, those are computed at generation time
-- and returned in the API response only, never persisted.
-- ============================================================

ALTER TABLE walkthrough_steps
  ADD COLUMN IF NOT EXISTS role TEXT,
  ADD COLUMN IF NOT EXISTS group_label TEXT;

-- ============================================================
-- Migration: replace_walkthrough_steps() RPC — updated to accept
-- role + group_label. Same atomic delete+insert pattern, same
-- transaction guarantee as before. No signature-breaking change
-- for existing callers: both new keys are optional in the JSONB
-- rows (COALESCE to NULL if absent).
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
        role,
        group_label,
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
        r->>'role',
        r->>'group_label',
        (r->>'source_updated_at')::TIMESTAMPTZ
    FROM jsonb_array_elements(p_rows) AS r;
END;
$$;