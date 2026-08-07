// components/chat/ChatInput.tsx — RepoMind Week 4, Milestone 5
//
// Owns: local draft-text state (never touches useChat's message list
// until actually sent), auto-resize behavior, the send interaction
// (button + Enter-to-send/Shift+Enter-for-newline), the 2000-char limit
// (client-side UX mirror of the backend's real enforcement in
// routers/chat.py::ChatRequest), disabling itself while streaming, and
// restoring focus to the textarea once streaming completes.

import { useState, useRef, useLayoutEffect, useEffect, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean; // true while isStreaming
}

const MAX_LENGTH = 2000; // mirrors backend ChatRequest.message max_length
const COUNTER_THRESHOLD = 1800; // only show the counter once this close to the limit
const MIN_ROWS_PX = 40; // ~single line
const MAX_HEIGHT_PX = 168; // ~6-8 lines before internal scroll kicks in

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize: reset to min height, then grow to fit content up to the
  // cap. Runs synchronously before paint so the resize is never visibly
  // delayed by a frame, same reasoning as MessageList's scroll effect.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = `${MIN_ROWS_PX}px`;
    const nextHeight = Math.min(el.scrollHeight, MAX_HEIGHT_PX);
    el.style.height = `${nextHeight}px`;
  }, [value]);

  // Restore focus once a streamed response finishes (disabled: true ->
  // false), so the user can keep asking questions without re-clicking
  // the input. Never fires while becoming disabled (streaming start) —
  // only on the false transition, and only via this effect, so focus is
  // never stolen mid-stream.
  const wasDisabledRef = useRef(disabled);
  useEffect(() => {
    if (wasDisabledRef.current && !disabled) {
      textareaRef.current?.focus();
    }
    wasDisabledRef.current = disabled;
  }, [disabled]);

  const trimmedLength = value.trim().length;
  const canSend = trimmedLength > 0 && trimmedLength <= MAX_LENGTH && !disabled;

  const handleSend = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");

    // Explicit immediate reset rather than waiting for the value-driven
    // useLayoutEffect above to run — avoids a brief mismatch where the
    // textarea would otherwise still show its previous (possibly
    // multi-line) height for one frame right after a long message sends.
    const el = textareaRef.current;
    if (el) {
      el.style.height = `${MIN_ROWS_PX}px`;
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter falls through to default textarea behavior (newline)
  };

  const showCounter = value.length >= COUNTER_THRESHOLD;
  const overLimit = value.length > MAX_LENGTH;

  return (
    <div className="border-t border-neutral-800 pt-3">
      <div
        className={`flex items-end gap-2 bg-neutral-900 border rounded-xl px-3 py-2 transition-colors ${
          disabled ? "border-neutral-800/50 opacity-60" : "border-neutral-800"
        }`}
      >
        <label htmlFor="chat-message-input" className="sr-only">
          Ask a question about this repository
        </label>
        <textarea
          id="chat-message-input"
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask a question about this repository..."
          rows={1}
          style={{ height: MIN_ROWS_PX, maxHeight: MAX_HEIGHT_PX }}
          className="flex-1 resize-none bg-transparent text-neutral-100 text-sm placeholder:text-neutral-600 focus:outline-none disabled:cursor-not-allowed overflow-y-auto"
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            canSend
              ? "bg-brand-500 text-white hover:bg-brand-400 cursor-pointer"
              : "bg-neutral-800 text-neutral-600 cursor-not-allowed"
          }`}
        >
          Send
        </button>
      </div>

      {showCounter && (
        <p
          className={`text-xs mt-1 text-right ${
            overLimit ? "text-red-400" : "text-neutral-500"
          }`}
        >
          {value.length} / {MAX_LENGTH}
        </p>
      )}
    </div>
  );
}