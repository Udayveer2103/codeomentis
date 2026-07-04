-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ── repos ────────────────────────────────────────────────────────────────────
CREATE TABLE repos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  github_url TEXT NOT NULL,
  owner TEXT NOT NULL,
  name TEXT NOT NULL,
  default_branch TEXT DEFAULT 'main',
  language_stats JSONB DEFAULT '{}',
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','indexing','ready','error')),
  error_message TEXT,
  file_count INT DEFAULT 0,
  architecture_pattern TEXT,
  architecture_summary TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE repos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own repos" ON repos
  FOR ALL USING (auth.uid() = user_id);

-- ── file_scores ───────────────────────────────────────────────────────────────
CREATE TABLE file_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id UUID REFERENCES repos(id) ON DELETE CASCADE NOT NULL,
  file_path TEXT NOT NULL,
  language TEXT,
  cc_score FLOAT DEFAULT 0,
  coupling_score FLOAT DEFAULT 0,
  todo_density FLOAT DEFAULT 0,
  fn_length_score FLOAT DEFAULT 0,
  composite_score FLOAT DEFAULT 0,
  severity TEXT DEFAULT 'low' CHECK (severity IN ('low','medium','high')),
  line_count INT DEFAULT 0,
  function_count INT DEFAULT 0,
  todo_count INT DEFAULT 0
);

ALTER TABLE file_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own file_scores" ON file_scores
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM repos
      WHERE repos.id = file_scores.repo_id
      AND repos.user_id = auth.uid()
    )
  );

-- ── code_chunks ───────────────────────────────────────────────────────────────
CREATE TABLE code_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id UUID REFERENCES repos(id) ON DELETE CASCADE NOT NULL,
  file_path TEXT NOT NULL,
  function_name TEXT,
  chunk_type TEXT CHECK (chunk_type IN ('function','class','module')),
  start_line INT,
  end_line INT,
  content TEXT NOT NULL,
  embedding vector(768)
);

ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own code_chunks" ON code_chunks
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM repos
      WHERE repos.id = code_chunks.repo_id
      AND repos.user_id = auth.uid()
    )
  );

-- Vector similarity search function (used by RAG in Week 3)
CREATE OR REPLACE FUNCTION match_chunks(
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
    1 - (code_chunks.embedding <=> query_embedding) AS similarity
  FROM code_chunks
  WHERE code_chunks.repo_id = match_repo_id
  ORDER BY code_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- ── chat_messages ─────────────────────────────────────────────────────────────
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id UUID REFERENCES repos(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own chat_messages" ON chat_messages
  FOR ALL USING (auth.uid() = user_id);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER repos_updated_at
  BEFORE UPDATE ON repos
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
