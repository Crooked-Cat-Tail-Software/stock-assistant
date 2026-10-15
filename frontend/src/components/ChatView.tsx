import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";

interface Props {
  sessionId: string | null;
  initialQuestion?: string;
  onSessionCreated: (id: string) => void;
  onTurnComplete: () => void;
}

const EXAMPLES = [
  "What is AAPL's latest price?",
  "What are today's top gainers and losers?",
  "Compare MSFT and GOOGL over the past month.",
];

export function ChatView({ sessionId, initialQuestion, onSessionCreated, onTurnComplete }: Props) {
  const { messages, loading, sending, error, send } = useChat({
    sessionId,
    onSessionCreated,
    onTurnComplete,
  });
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  return (
    <section className="chat" aria-label="Conversation">
      <div className="chat__log" aria-live="polite" aria-busy={loading || sending}>
        {loading && <p className="muted">Loading conversation…</p>}

        {!loading && messages.length === 0 && !sending && (
          <div className="empty">
            <h2>Ask a market question</h2>
            <p className="muted">Answers use live data from Alpha Vantage. For example:</p>
            <ul className="empty__examples">
              {EXAMPLES.map((example) => (
                <li key={example}>
                  <button type="button" className="link" disabled={sending} onClick={() => void send(example)}>
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {sending && (
          <p className="thinking" role="status">
            Researching… fetching market data can take up to 30 seconds.
          </p>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <p className="banner banner--error" role="alert">
          {error}
        </p>
      )}

      <Composer initialText={initialQuestion} disabled={sending || loading} onSend={send} />
      <p className="disclaimer">Informational only. This is not investment advice.</p>
    </section>
  );
}
