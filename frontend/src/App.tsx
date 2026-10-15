import { useCallback, useState } from "react";
import { ChatView } from "./components/ChatView";
import { HealthBadge } from "./components/HealthBadge";
import { SessionList } from "./components/SessionList";
import { Watchlist } from "./components/Watchlist";
import { useSessions } from "./hooks/useSessions";
import { watchlistPrompt } from "./lib/validation";

interface OpenChat {
  /** React key: changes only when the user opens a different chat. */
  key: string;
  sessionId: string | null;
  initialQuestion?: string;
}

let draftCounter = 0;
const newDraft = (initialQuestion?: string): OpenChat => ({
  key: `draft-${++draftCounter}`,
  sessionId: null,
  initialQuestion,
});

export default function App() {
  const { sessions, loading, error, refresh, remove } = useSessions();
  const [chat, setChat] = useState<OpenChat>(() => newDraft());

  const openSession = (id: string) => setChat({ key: id, sessionId: id });

  const onSessionCreated = useCallback((id: string) => {
    // Keep the same key so the chat on screen isn't remounted.
    setChat((current) => ({ ...current, sessionId: id }));
  }, []);

  const onTurnComplete = useCallback(() => void refresh(), [refresh]);

  async function deleteSession(id: string) {
    const title = sessions.find((s) => s.id === id)?.title ?? "this conversation";
    if (!window.confirm(`Delete “${title}”? This can’t be undone.`)) return;
    if ((await remove(id)) && chat.sessionId === id) setChat(newDraft());
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>Stock Research Assistant</h1>
        <HealthBadge />
      </header>

      <aside className="app__sidebar">
        <button type="button" className="primary" onClick={() => setChat(newDraft())}>
          + New chat
        </button>
        <SessionList
          sessions={sessions}
          activeId={chat.sessionId}
          loading={loading}
          error={error}
          onSelect={openSession}
          onDelete={(id) => void deleteSession(id)}
        />
        <Watchlist onAsk={(symbol) => setChat(newDraft(watchlistPrompt(symbol)))} />
      </aside>

      <main className="app__main">
        <ChatView
          key={chat.key}
          sessionId={chat.sessionId}
          initialQuestion={chat.initialQuestion}
          onSessionCreated={onSessionCreated}
          onTurnComplete={onTurnComplete}
        />
      </main>
    </div>
  );
}
