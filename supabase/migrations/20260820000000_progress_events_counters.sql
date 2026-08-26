-- ============================================================
-- Adds structured progress counters to progress_events.
-- Additive only: every column is nullable, so existing rows
-- (and the existing SSE stream in routers/ingest.py, which
-- selects only id/stage/progress/message) are unaffected.
-- The ingestion pipeline populates a counter only when it
-- already has that exact number in scope at that point — never
-- inferred or backfilled from progress percentage.
-- ============================================================

ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS files_processed INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS total_files INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS functions_extracted INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS chunks_created INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS total_chunks INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS graph_nodes INT;
ALTER TABLE progress_events ADD COLUMN IF NOT EXISTS graph_edges INT;