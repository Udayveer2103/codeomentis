-- Additive only. Does not touch any existing table, RPC, or the
-- call graph storage bucket. Impact Analyzer's graph computation
-- (BFS over call_graph.json) remains uncached and is recomputed
-- on every request, since it is already fast and free. Only the
-- LLM-derived reasoning fields are cached here.
--
-- analysis_fingerprint pins a cached row to the exact repository
-- analysis content it was generated from (currently derived from
-- call_graph.json, but named implementation-agnostically so the
-- underlying source can change without a schema change).
--
-- analysis_version lets a future prompt/schema change invalidate
-- old cached rows without any TTL or cleanup job — bump the
-- constant in code and every existing row simply stops matching.
--
-- No time-based expiry: a row stays valid indefinitely until either
-- the fingerprint or the version no longer matches, at which point
-- it's treated as stale on next lookup (self-correcting).

CREATE TABLE IF NOT EXISTS impact_ai_cache (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id uuid NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    query_node text NOT NULL,
    analysis_fingerprint text NOT NULL,
    analysis_version text NOT NULL DEFAULT 'v1',
    ai_summary text,
    safe_to_change boolean,
    risk_level text,
    risk_reasons jsonb,
    possible_regressions jsonb,
    suggested_test_cases jsonb,
    refactoring_advice text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repo_id, query_node)
);

CREATE INDEX IF NOT EXISTS idx_impact_ai_cache_repo_node
    ON impact_ai_cache (repo_id, query_node);