// components/chat/MessageList.tsx — CodeoMentis Week 4, Milestone 5
//
// Owns: scroll container, auto-scroll behavior, empty state, composing
// ChatMessage components. useChat.ts stays UI-agnostic — it has no
// knowledge of scrolling; all of that logic lives here.
//
// Auto-scroll only fires when the user was already near the bottom
// BEFORE new content arrived. "Near bottom" is tracked continuously via
// the onScroll handler — which only fires on actual user scroll
// actions, not on content growth — so by the time a new message/token
// triggers the layout effect, wasNearBottomRef already reflects the
// pre-update state, never something measured after the new content has
// already changed the layout.
//
// useLayoutEffect (not useEffect) performs the scroll adjustment
// synchronously after the DOM commits but before the browser paints —
// this avoids a visible micro-jump on every streamed token that
// useEffect's post-paint timing would otherwise cause.
//
// The scroll container stays mounted at all times, including when
// messages is empty — the empty state renders as content inside it,
// not as an alternate returned tree. Keeps layout stable and makes
// future scroll-related features (history loading indicators, scroll
// restoration, virtualization) straightforward to add without
// restructuring the mount point.

import { useLayoutEffect, useRef } from "react";
import type { ChatMessageData, SourceMetadata } from "@/types/chat";
import { ChatMessage } from "./ChatMessage";

interface MessageListProps {
  messages: ChatMessageData[];
  onSourceClick?: (source: SourceMetadata) => void;
}

// Distance (px) from the bottom within which we still consider the user
// "at the bottom" — accounts for sub-pixel rounding and minor scroll
// noise rather than requiring an exact 0.
const BOTTOM_THRESHOLD_PX = 80;

export function MessageList({ messages, onSourceClick }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wasNearBottomRef = useRef(true);

  // Updated only by real scroll events (user scrolling, or our own
  // programmatic scroll-to-bottom below, which itself fires a scroll
  // event and correctly resets this to true). Content growth alone
  // never triggers a scroll event, so this always reflects the state
  // as of before the most recent content change — never something
  // computed after the fact.
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;

    const distanceFromBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight;
    wasNearBottomRef.current = distanceFromBottom <= BOTTOM_THRESHOLD_PX;
  };

  // Runs synchronously after the DOM has committed the new messages but
  // before the browser paints — the scroll position is corrected before
  // the user ever sees the pre-scroll frame, keeping rapid token
  // streaming visually smooth instead of jumping on each update.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    if (wasNearBottomRef.current) {
      el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
    }
  }, [messages]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto flex flex-col gap-4 px-1 py-2"
    >
      {messages.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-neutral-500 text-sm text-center max-w-xs">
            Ask a question about this repository to get started.
          </p>
        </div>
      ) : (
        messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            onSourceClick={onSourceClick}
          />
        ))
      )}
    </div>
  );
}