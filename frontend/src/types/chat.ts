// types/chat.ts — RepoMind Week 4, Milestone 5
//
// Shared types for the chat feature, kept independent of any specific
// hook or component so both layers (useChat.ts, and presentational
// components like SourceCard.tsx/ChatMessage.tsx/MessageList.tsx) can
// depend on the same definitions without components depending on hook
// internals.

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
  sources?: SourceMetadata[]; // assistant messages only; absent on reloaded history (see backend note in routers/chat.py::get_chat_history)
  status: MessageStatus; // user messages are always "complete"
  errorMessage?: string; // populated only when status === "error"
}