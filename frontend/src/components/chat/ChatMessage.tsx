// components/chat/ChatMessage.tsx — CodeoMentis Week 4, Milestone 5
//
// Renders one message bubble. User messages are right-aligned, simple
// text only. Assistant messages are left-aligned and own: streamed
// content, streaming/error indicators, and source cards — rendered
// BELOW the bubble (supporting evidence), not nested inside it.
//
// MessageContent has a single responsibility: render one message body
// from a plain string. It never knows about streaming state, errors, or
// sources — those are AssistantMessage's concern — so markdown support
// later only touches MessageContent's internals.
//
// UserMessage/AssistantMessage each receive only the specific fields
// they use, not the whole ChatMessageData object — keeps coupling
// explicit and each component's actual data dependency visible at a
// glance.
//
// Imports types from types/chat.ts, not from useChat.ts.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessageData, MessageStatus, SourceMetadata } from "@/types/chat";
import { SourceCard } from "./SourceCard";

interface ChatMessageProps {
  message: ChatMessageData;
  onSourceClick?: (source: SourceMetadata) => void;
}

// ── Content rendering (markdown-ready extension point) ──────────────────────────

function MessageContent({ content }: { content: string }) {
  return (
    <div className="prose prose-invert max-w-none prose-pre:bg-neutral-950 prose-code:text-sky-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

// ── Streaming indicator ──────────────────────────────────────────────────────────

function StreamingCursor() {
  return (
    <span className="inline-block w-1.5 h-3.5 bg-brand-400 animate-pulse ml-0.5 align-middle" />
  );
}

// ── User message ──────────────────────────────────────────────────────────────────

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] bg-brand-500/20 border border-brand-500/30 rounded-xl rounded-br-sm px-4 py-2.5 text-neutral-100 text-sm">
        <MessageContent content={content} />
      </div>
    </div>
  );
}

// ── Assistant message ────────────────────────────────────────────────────────────

interface AssistantMessageProps {
  content: string;
  status: MessageStatus;
  errorMessage?: string;
  sources?: SourceMetadata[];
  onSourceClick?: (source: SourceMetadata) => void;
}

function AssistantMessage({
  content,
  status,
  errorMessage,
  sources,
  onSourceClick,
}: AssistantMessageProps) {
  const isStreaming = status === "streaming";
  const isError = status === "error";

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex flex-col gap-2">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl rounded-bl-sm px-4 py-2.5 text-neutral-200 text-sm">
          <MessageContent content={content} />
          {isStreaming && <StreamingCursor />}

          {isError && (
            <p className="text-red-400 text-xs mt-2">
              {errorMessage ?? "Something went wrong."}
            </p>
          )}
        </div>

        {sources && sources.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {sources.map((source) => (
              <SourceCard
                key={source.chunk_id}
                source={source}
                onClick={onSourceClick}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Public component ─────────────────────────────────────────────────────────────

export function ChatMessage({ message, onSourceClick }: ChatMessageProps) {
  if (message.role === "user") {
    return <UserMessage content={message.content} />;
  }

  return (
    <AssistantMessage
      content={message.content}
      status={message.status}
      errorMessage={message.errorMessage}
      sources={message.sources}
      onSourceClick={onSourceClick}
    />
  );
}