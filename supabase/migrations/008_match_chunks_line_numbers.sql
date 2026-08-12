-- ============================================================
-- Migration: match_chunks() — add start_line/end_line
-- Feature: Chat/RAG (Week 4, Milestone 5)
--
-- Purpose: the original match_chunks() (from the initial schema
-- migration) did not return start_line/end_line, even though
-- code_chunks has both columns. Chat/RAG's structured source
-- metadata requirement needs line numbers for "jump to source"
-- functionality, and fetching them via a second per-chunk query
-- would add unnecessary round trips. Because PostgreSQL does not allow changing the RETURNS TABLE definition
-- using CREATE OR REPLACE FUNCTION, this migration drops and recreates the
-- function with the expanded return type. No table data is modified.
--
-- Also adds a defensive `embedding IS NOT NULL` filter. No effect
-- on fully-ingested repos (embeddings are always populated per
-- embed_functions()), but protects against partially-ingested
-- repos or future edge cases where a row's embedding could be
-- null, which would otherwise error inside the <=> distance
-- operator rather than simply excluding that row.
-- ============================================================
DROP FUNCTION IF EXISTS public.match_chunks(vector, uuid, integer);

CREATE FUNCTION public.match_chunks(
  query_embedding vector(768),
  match_repo_id UUID,
  match_count INT DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  file_path TEXT,
  function_name TEXT,
  chunk_type TEXT,
  content TEXT,
  start_line INT,
  end_line INT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    code_chunks.id,
    code_chunks.file_path,
    code_chunks.function_name,
    code_chunks.chunk_type,
    code_chunks.content,
    code_chunks.start_line,
    code_chunks.end_line,
    1 - (code_chunks.embedding <=> query_embedding) AS similarity
  FROM code_chunks
  WHERE code_chunks.repo_id = match_repo_id
    AND code_chunks.embedding IS NOT NULL
  ORDER BY code_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;