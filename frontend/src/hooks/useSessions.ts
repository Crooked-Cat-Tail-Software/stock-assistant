import { useCallback, useEffect, useState } from "react";
import { useApi } from "../api/ApiContext";
import type { SessionSummary } from "../api/client";
import { errorMessage } from "../lib/errors";

export function useSessions() {
  const api = useApi();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    api
      .listSessions()
      .then((data) => !cancelled && setSessions(data))
      .catch((e) => !cancelled && setError(errorMessage(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [api]);

  const remove = useCallback(
    async (id: string) => {
      try {
        await api.deleteSession(id);
        setSessions((current) => current.filter((s) => s.id !== id));
        setError(null);
        return true;
      } catch (e) {
        setError(errorMessage(e));
        return false;
      }
    },
    [api],
  );

  return { sessions, loading, error, refresh, remove };
}
