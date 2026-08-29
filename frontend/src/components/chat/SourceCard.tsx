// components/chat/SourceCard.tsx — CodeoMentis Week 4, Milestone 5
//
// Presentational only: renders one retrieved source (file/function/line
// range). similarity is intentionally NOT rendered per Milestone 5 scope
// — it stays in the SourceMetadata type for later use (sorting,
// debug/dev mode, future UI), just not displayed here.
//
// Uses a semantic <button> when interactive (onClick provided) and a
// plain <div> when not — native button handles keyboard/focus behavior
// correctly with no manual role/tabIndex/onKeyDown recreation needed.
// SourceContent is extracted so the inner layout has exactly one
// implementation shared by both the button and div cases — future
// additions (language badge, GitHub icon, copy-path button, jump
// indicator) only need to change one place.
//
// Imports SourceMetadata from types/chat.ts, not from useChat.ts — this
// is a presentational component and should not depend on hook modules.

import type { SourceMetadata } from "@/types/chat";

interface SourceCardProps {
  source: SourceMetadata;
  onClick?: (source: SourceMetadata) => void;
}

const CARD_CLASSES =
  "bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-left w-full";
const INTERACTIVE_CLASSES =
  "cursor-pointer hover:border-brand-500/50 hover:bg-neutral-800/60 transition-colors";

function SourceContent({ source }: { source: SourceMetadata }) {
  const lineRange =
    source.start_line !== null && source.end_line !== null
      ? `Lines ${source.start_line}\u2013${source.end_line}`
      : null;

  return (
    <>
      <p className="text-neutral-300 text-xs font-mono truncate">
        {source.file_path}
      </p>
      {source.function_name && (
        <p className="text-neutral-500 text-xs font-mono">
          Function: {source.function_name}
        </p>
      )}
      {lineRange && (
        <p className="text-neutral-600 text-xs mt-0.5">{lineRange}</p>
      )}
    </>
  );
}

export function SourceCard({ source, onClick }: SourceCardProps) {
  if (onClick) {
    return (
      <button
        type="button"
        onClick={() => onClick(source)}
        className={`${CARD_CLASSES} ${INTERACTIVE_CLASSES}`}
      >
        <SourceContent source={source} />
      </button>
    );
  }                                                   

  return (
    <div className={CARD_CLASSES}>
      <SourceContent source={source} />
    </div>
  );
}