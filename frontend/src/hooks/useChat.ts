// hooks/useChat.ts — CodeoMentis Week 4, Milestone 5
//
// Plain custom hook (no TanStack Query) — chat is a long-lived streaming
// session, not a cacheable request/response value, so it doesn't fit the
// useQuery pattern used by useHeatmap/useImpact/useWalkthrough.
//
// Owns: conversation state, streaming lifecycle, SSE parsing (via
// utils/sse.ts), initial history load, separate history/chat error
// states, send/reset. UI-agnostic — no scrolling or rendering decisions
// live here (see components/chat/MessageList.tsx for auto-scroll).

import { supabase } from "@/lib/supabase";
import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { extractSSEFrames, type SSEFrame } from "@/utils/sse";

// TODO(#1): confirm the real export from lib/api.ts. Assumed here as
// API_BASE_URL — a raw fetch() call (needed for streaming; api.post
// almost certainly isn't stream-aware) needs the same base URL api.get
// uses internally, rather than a hardcoded relative path assuming
// same-origin frontend/backend.
import { API_BASE_URL } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface SourceMetadata {
  chunk_id: string;
  file_path: string;
  function_name: string | null;
  similarity: number;
  start_line: number | null;
  end_line: number | null;
}

export type MessageStatus = "streaming" | "complete" | "error";

export interface ChatMessageData {
  id: string; // client-generated for React keys/state updates
  role: "user" | "assistant";
  content: string;
  sources?: SourceMetadata[]; // assistant messages only; absent on reloaded history (see backend note)
  status: MessageStatus; // user messages are always "complete"
  errorMessage?: string; // populated only when status === "error"
}

interface ChatHistoryResponse {
  repo_id: string;
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
  }>;
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useChat(repoId: string) {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Separate error states (#5) — a failed history load and a failed
  // streamed response are different UX situations and shouldn't share
  // one flag: a history-load failure means "we don't know what was
  // said before," a chat failure means "this one message didn't work,"
  // and the UI should treat them very differently (e.g. a chat error
  // shouldn't wipe out an already-loaded, valid conversation).
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const abortActiveStream = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  }, []);

  // ── Load persisted history whenever repoId changes ──────────────────────────
  useEffect(() => {
    let cancelled = false;

    // #4: abort any in-flight stream from the previous repo, and clear
    // its messages immediately — before the new history request even
    // starts — so the old repo's conversation never briefly flashes
    // under the new repoId.
    abortActiveStream();
    setMessages([]);
    setIsStreaming(false);
    setChatError(null);
    setHistoryError(null);
    setHistoryLoading(true);

    async function loadHistory() {
      try {
        const res = await api.get<ChatHistoryResponse>(
          `/api/chat/${repoId}/messages`
        );
        if (cancelled) return;

        const loaded: ChatMessageData[] = res.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          status: "complete",
          // sources intentionally absent — not persisted this milestone,
          // see backend note in routers/chat.py::get_chat_history
        }));
        setMessages(loaded);
      } catch (err) {
        if (!cancelled) {
          setHistoryError(
            err instanceof Error ? err.message : "Failed to load conversation history."
          );
        }
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [repoId, abortActiveStream]);

  // ── Abort in-flight stream on unmount ────────────────────────────────────────
  useEffect(() => {
    return () => {
      abortActiveStream();
    };
  }, [abortActiveStream]);

  // ── Send a message ───────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setChatError(null);

      const userMessage: ChatMessageData = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        status: "complete",
      };

      const assistantId = crypto.randomUUID();
      const assistantPlaceholder: ChatMessageData = {
        id: assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const updateAssistant = (patch: Partial<ChatMessageData>) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, ...patch } : m))
        );
      };

      const appendToAssistant = (delta: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + delta } : m
          )
        );
      };

      const handleFrame = (frame: SSEFrame): "continue" | "stop" => {
        switch (frame.event) {
          case "sources": {
            const data = frame.data as { sources: SourceMetadata[] };
            updateAssistant({ sources: data.sources });
            return "continue";
          }
          case "token": {
            const data = frame.data as { text: string };
            appendToAssistant(data.text);
            return "continue";
          }
          case "error": {
            const data = frame.data as { message: string };
            updateAssistant({ status: "error", errorMessage: data.message });
            setChatError(data.message);
            return "stop"; // error is terminal — backend won't send more frames
          }
          case "done": {
            // #3: `done` is the authoritative completion signal, not the
            // reader loop ending on its own. Mark complete and signal
            // the caller to stop reading immediately.
            updateAssistant({ status: "complete" });
            return "stop";
          }
          default:
            // Gracefully ignore unknown event types (#2) — forward
            // compatible with future backend event additions.
            return "continue";
        }
      };

      try {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("You must be logged in to use chat.");
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ repo_id: repoId, message: trimmed }),
    signal: controller.signal,
  });

        if (!response.ok || !response.body) {
          const errBody = await response.json().catch(() => null);
          throw new Error(errBody?.detail || `Request failed (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let shouldStop = false;

        while (!shouldStop) {
          const { value, done: streamDone } = await reader.read();
          if (streamDone) break;

          buffer += decoder.decode(value, { stream: true });

          const { frames, remaining } = extractSSEFrames(buffer);
          buffer = remaining;

          for (const frame of frames) {
            if (handleFrame(frame) === "stop") {
              shouldStop = true;
              break;
            }
          }
        }

        if (shouldStop) {
          await reader.cancel(); // release the underlying stream promptly
        }
      } catch (err) {
        if (controller.signal.aborted) {
          // Aborted deliberately (unmount/repo-change/reset) — silent,
          // no user-facing error (#9).
          return;
        }
        const message =
          err instanceof Error ? err.message : "Something went wrong. Please try again.";
        updateAssistant({ status: "error", errorMessage: message });
        setChatError(message);
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [repoId, isStreaming]
  );

  // ── Reset ─────────────────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    abortActiveStream();
    setMessages([]);
    setIsStreaming(false);
    setChatError(null);
    setHistoryError(null);
  }, [abortActiveStream]);

  return {
    messages,
    isStreaming,
    historyLoading,
    historyError,
    chatError,
    sendMessage,
    reset,
  };
}