import { useCallback, useEffect, useState } from "react";
import { useApi } from "../api/ApiContext";
import type { Message } from "../api/client";
import { errorMessage } from "../lib/errors";

interface Options {
  /** null means a new chat that has no session in the database yet. */
  sessionId: string | null;
  /** Called after the first question creates the session. */
  onSessionCreated: (id: string) => void;
  /** Called after each answered question, e.g. to refresh the session list. */
  onTurnComplete: () => void;
}

/**
 * State for one open chat. The parent gives each opened chat its own React
 * `key`, so switching chats remounts this hook with fresh state. Creating the
 * session on the first question keeps the same key, so the messages on screen
 * are kept.
 */
export function useChat({ sessionId, onSessionCreated, onTurnComplete }: Options) {
  const api = useApi();
  const [initialId] = useState(sessionId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(initialId !== null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialId === null) return;
    let cancelled = false;
    api
      .getSession(initialId)
      .then((detail) => !cancelled && setMessages(detail.messages))
      .catch((e) => !cancelled && setError(errorMessage(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [api, initialId]);

  /** Returns true if the question was answered (so the composer can clear). */
  const send = useCallback(
    async (content: string): Promise<boolean> => {
      setSending(true);
      setError(null);
      // Show the question right away while the agent works (it can take ~30 s).
      const pending: Message = {
        id: `pending-${Date.now()}`,
        role: "user",
        content,
        tool_calls: [],
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, pending]);

      try {
        let id = sessionId;
        if (id === null) {
          id = (await api.createSession()).id;
          onSessionCreated(id);
        }
        const turn = await api.sendMessage(id, content);
        setMessages((current) => [
          ...current.filter((m) => m.id !== pending.id),
          turn.user_message,
          turn.assistant_message,
        ]);
        return true;
      } catch (e) {
        // Nothing was saved, so take the question back off the screen.
        setMessages((current) => current.filter((m) => m.id !== pending.id));
        setError(errorMessage(e));
        return false;
      } finally {
        setSending(false);
        onTurnComplete();
      }
    },
    [api, sessionId, onSessionCreated, onTurnComplete],
  );

  return { messages, loading, sending, error, send };
}
