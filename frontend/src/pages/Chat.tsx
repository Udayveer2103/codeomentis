// pages/Chat.tsx — RepoMind Week 4, Milestone 5
//
// Chat/RAG page. Thin shell: layout + UI state coordination only. All
// conversation state, streaming, and SSE handling live in useChat.ts.
// MessageList owns scrolling/composition; ChatInput owns the send
// interaction. This page's only job is wiring them together and
// deciding which state (history loading/error vs. chat error) governs
// what's shown.
//
// Uses Header/Sidebar as default imports, matching the fix applied to
// Walkthrough.tsx (RepoDetail.tsx confirmed these are default exports).
//
// Layout uses flex-1/flex-col/min-h-0 rather than h-screen — the outer
// layout (Header + Sidebar + this main) already owns viewport height;
// h-screen on a nested element would create a second viewport-height
// calculation and risk double scrolling or overflow below the header.
// min-h-0 is required so MessageList's flex-1/overflow-y-auto can
// actually shrink within the column instead of growing to fit content.

import { useParams, Link } from "react-router-dom";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useChat } from "@/hooks/useChat";
import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";

export default function Chat() {
  const { repoId } = useParams<{ repoId: string }>();

  if (!repoId) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col dark">
        <Header />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 p-6 max-w-3xl mx-auto w-full">
            <Alert variant="destructive">
              <AlertDescription>Invalid repository.</AlertDescription>
            </Alert>
          </main>
        </div>
      </div>
    );
  }

  const {
    messages,
    isStreaming,
    historyLoading,
    historyError,
    chatError,
    sendMessage,
  } = useChat(repoId);

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col dark">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 flex flex-col p-6 max-w-3xl mx-auto w-full min-h-0">
          <div className="mb-4 shrink-0">
            <Link
              to={`/repo/${repoId}`}
              className="text-neutral-400 text-sm hover:text-neutral-200"
            >
              ← Back to repo
            </Link>
            <h1 className="font-display text-2xl text-neutral-100 mt-2">
              Chat with Repo
            </h1>
          </div>

          {historyLoading && (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-neutral-500 text-sm">
                Loading conversation...
              </p>
            </div>
          )}

          {!historyLoading && historyError && (
            <div className="flex-1 flex items-center justify-center">
              <Alert variant="destructive" className="max-w-md">
                <AlertDescription>{historyError}</AlertDescription>
              </Alert>
            </div>
          )}

          {!historyLoading && !historyError && (
            <>
              <MessageList messages={messages} />

              {chatError && (
                <Alert variant="destructive" className="mt-3 shrink-0">
                  <AlertDescription>{chatError}</AlertDescription>
                </Alert>
              )}

              <div className="shrink-0 mt-3">
                <ChatInput onSend={sendMessage} disabled={isStreaming} />
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}