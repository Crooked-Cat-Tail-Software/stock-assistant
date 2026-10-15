import { useCallback, useEffect, useState } from "react";
import { useApi } from "../api/ApiContext";
import type { WatchlistItem } from "../api/client";
import { errorMessage } from "../lib/errors";

export function useWatchlist() {
  const api = useApi();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listWatchlist()
      .then((data) => !cancelled && setItems(data))
      .catch((e) => !cancelled && setError(errorMessage(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [api]);

  /** Returns an error message to show next to the form, or null on success. */
  const add = useCallback(
    async (symbol: string, note: string): Promise<string | null> => {
      try {
        const item = await api.addWatchlistItem({
          symbol: symbol.trim(),
          note: note.trim() || undefined,
        });
        setItems((current) =>
          [...current, item].sort((a, b) => a.symbol.localeCompare(b.symbol)),
        );
        return null;
      } catch (e) {
        return errorMessage(e);
      }
    },
    [api],
  );

  const remove = useCallback(
    async (symbol: string) => {
      try {
        await api.removeWatchlistItem(symbol);
        setItems((current) => current.filter((i) => i.symbol !== symbol));
        setError(null);
      } catch (e) {
        setError(errorMessage(e));
      }
    },
    [api],
  );

  return { items, loading, error, add, remove };
}
