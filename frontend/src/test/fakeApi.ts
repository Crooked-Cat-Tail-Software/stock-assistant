import { vi } from "vitest";
import { ApiError, type Api, type Message, type SessionDetail, type WatchlistItem } from "../api/client";

/**
 * In-memory stand-in for the backend that follows the same rules as
 * openapi.yaml (uppercased symbols, 409 on duplicates, 404 on unknown ids).
 * Every method is a vi.fn, so tests can assert calls or override behavior.
 */
export function createFakeApi(seed: { sessions?: SessionDetail[]; watchlist?: WatchlistItem[] } = {}) {
  const sessions = new Map<string, SessionDetail>((seed.sessions ?? []).map((s) => [s.id, s]));
  const watchlist = new Map<string, WatchlistItem>((seed.watchlist ?? []).map((w) => [w.symbol, w]));
  let counter = 0;
  const now = () => new Date(Date.UTC(2026, 9, 15, 12, 0, counter++)).toISOString();
  const id = () => `00000000-0000-4000-8000-${String(++counter).padStart(12, "0")}`;

  const summary = (s: SessionDetail) => {
    const { messages, ...rest } = s;
    return { ...rest, message_count: messages.length };
  };
  const find = (sessionId: string) => {
    const s = sessions.get(sessionId);
    if (!s) throw new ApiError(404, "not_found", "Session not found");
    return s;
  };

  const api: Api = {
    getHealth: vi.fn(async () => ({ status: "ok" as const, database: "ok" as const, version: "test" })),
    listSessions: vi.fn(async () =>
      [...sessions.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(summary),
    ),
    createSession: vi.fn(async (title?: string) => {
      const t = now();
      const s: SessionDetail = { id: id(), title: title ?? null, message_count: 0, created_at: t, updated_at: t, messages: [] };
      sessions.set(s.id, s);
      return summary(s);
    }),
    getSession: vi.fn(async (sessionId: string) => {
      const s = find(sessionId);
      return { ...s, message_count: s.messages.length };
    }),
    deleteSession: vi.fn(async (sessionId: string) => {
      find(sessionId);
      sessions.delete(sessionId);
    }),
    sendMessage: vi.fn(async (sessionId: string, content: string) => {
      const s = find(sessionId);
      const ticker = content.match(/\b[A-Z]{2,5}\b/)?.[0];
      const user: Message = { id: id(), role: "user", content, tool_calls: [], created_at: now() };
      const assistant: Message = {
        id: id(),
        role: "assistant",
        content: ticker ? `**${ticker}** is at $123.45.` : "Here is your answer.",
        tool_calls: ticker ? [{ name: "GLOBAL_QUOTE", arguments: { symbol: ticker } }] : [],
        created_at: now(),
      };
      s.messages.push(user, assistant);
      s.title ??= content.slice(0, 80);
      s.updated_at = assistant.created_at;
      return { user_message: user, assistant_message: assistant };
    }),
    listWatchlist: vi.fn(async () => [...watchlist.values()].sort((a, b) => a.symbol.localeCompare(b.symbol))),
    addWatchlistItem: vi.fn(async ({ symbol, note }) => {
      const upper = symbol.toUpperCase();
      if (watchlist.has(upper)) throw new ApiError(409, "duplicate_symbol", `${upper} is already on the watchlist`);
      const item: WatchlistItem = { symbol: upper, note: note ?? null, created_at: now() };
      watchlist.set(upper, item);
      return item;
    }),
    removeWatchlistItem: vi.fn(async (symbol: string) => {
      if (!watchlist.delete(symbol.toUpperCase())) throw new ApiError(404, "not_found", "Watchlist symbol not found");
    }),
  };
  return api;
}

export function sessionFixture(overrides: Partial<SessionDetail> = {}): SessionDetail {
  const t = "2026-10-14T09:00:00Z";
  const messages: Message[] = overrides.messages ?? [
    { id: "m1", role: "user", content: "How is MSFT doing?", tool_calls: [], created_at: t },
    {
      id: "m2",
      role: "assistant",
      content: "MSFT closed at $400.",
      tool_calls: [{ name: "GLOBAL_QUOTE", arguments: { symbol: "MSFT" } }],
      created_at: t,
    },
  ];
  return {
    id: "11111111-1111-4111-8111-111111111111",
    title: "How is MSFT doing?",
    created_at: t,
    updated_at: t,
    ...overrides,
    messages,
    message_count: messages.length,
  };
}
