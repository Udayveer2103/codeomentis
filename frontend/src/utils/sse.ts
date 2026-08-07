// utils/sse.ts — RepoMind Week 4, Milestone 5
//
// Minimal SSE frame parser for manually-consumed streams (fetch() +
// ReadableStream), since EventSource can't be used for POST requests.
// Extracted from useChat.ts per SSE-compliance requirements: supports
// multiple `data:` lines per frame (concatenated with \n, per spec),
// ignores comment lines (":...") and blank lines, and gracefully
// returns frames with unrecognized event names rather than dropping
// them — the caller decides what to do with an unknown event type.

export interface SSEFrame {
  event: string;
  data: unknown;
}

/**
 * Parses one SSE frame block (the text between two "\n\n" boundaries).
 * Returns null only if the block has no event name or no data lines —
 * i.e. genuinely not a usable frame, not because the event name is
 * unrecognized (that's the caller's decision, not the parser's).
 */
export function parseSSEBlock(block: string): SSEFrame | null {
  let event = "";
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.trimEnd();

    if (line === "" || line.startsWith(":")) {
      continue; // blank line or SSE comment — ignore
    }

    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
    // other SSE fields (id:, retry:) intentionally ignored — unused by
    // this backend contract, but not treated as errors if present
  }

  if (!event || dataLines.length === 0) return null;

  const rawData = dataLines.join("\n");

  try {
    return { event, data: JSON.parse(rawData) };
  } catch {
    return null; // malformed JSON payload — drop the frame, don't throw
  }
}

/**
 * Splits an accumulating buffer on SSE frame boundaries ("\n\n"),
 * parsing each complete block found and returning the leftover
 * (possibly partial) buffer for the next read.
 */
export function extractSSEFrames(buffer: string): {
  frames: SSEFrame[];
  remaining: string;
} {
  const frames: SSEFrame[] = [];
  let working = buffer;

  let boundary = working.indexOf("\n\n");
  while (boundary !== -1) {
    const block = working.slice(0, boundary);
    working = working.slice(boundary + 2);

    const frame = parseSSEBlock(block);
    if (frame) frames.push(frame);

    boundary = working.indexOf("\n\n");
  }

  return { frames, remaining: working };
}