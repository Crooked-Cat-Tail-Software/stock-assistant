/**
 * The only module that talks to the backend (enforced by ESLint).
 *
 * One function per operation in openapi.yaml. Types come from
 * `schema.d.ts`, which is generated from the contract by `npm run gen:api`,
 * so a contract change that breaks the frontend fails `npm run typecheck`.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Health = Schemas["Health"];
export type SessionSummary = Schemas["SessionSummary"];
export type SessionDetail = Schemas["SessionDetail"];
export type Message = Schemas["Message"];
export type ToolCall = Schemas["ToolCall"];
export type ChatTurn = Schemas["ChatTurn"];
export type WatchlistItem = Schemas["WatchlistItem"];
export type WatchlistItemCreate = Schemas["WatchlistItemCreate"];

/** Every failure, whether HTTP error or network problem, surfaces as this one type. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  429: "Too many requests. Please wait a moment and try again.",
  502: "The assistant's data service failed. Please try again.",
  503: "The service is temporarily unavailable.",
  504: "The assistant took too long to respond. Please try again.",
};

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server. Check your connection.");
  }

  if (response.status === 204) return undefined as T;

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    // The backend always sends { code, message }, but a proxy in front of it may not.
    if (isErrorBody(data)) throw new ApiError(response.status, data.code, data.message);
    throw new ApiError(
      response.status,
      "http_error",
      FALLBACK_MESSAGES[response.status] ?? `Request failed (HTTP ${response.status}).`,
    );
  }
  return data as T;
}

function isErrorBody(data: unknown): data is Schemas["Error"] {
  return (
    typeof data === "object" &&
    data !== null &&
    typeof (data as Record<string, unknown>).code === "string" &&
    typeof (data as Record<string, unknown>).message === "string"
  );
}

const enc = encodeURIComponent;

export const api = {
  getHealth: () => request<Health>("GET", "/api/health"),

  listSessions: () => request<SessionSummary[]>("GET", "/api/sessions"),
  createSession: (title?: string) =>
    request<SessionSummary>("POST", "/api/sessions", title ? { title } : {}),
  getSession: (id: string) => request<SessionDetail>("GET", `/api/sessions/${enc(id)}`),
  deleteSession: (id: string) => request<void>("DELETE", `/api/sessions/${enc(id)}`),
  sendMessage: (id: string, content: string) =>
    request<ChatTurn>("POST", `/api/sessions/${enc(id)}/messages`, { content }),

  listWatchlist: () => request<WatchlistItem[]>("GET", "/api/watchlist"),
  addWatchlistItem: (item: WatchlistItemCreate) =>
    request<WatchlistItem>("POST", "/api/watchlist", item),
  removeWatchlistItem: (symbol: string) =>
    request<void>("DELETE", `/api/watchlist/${enc(symbol)}`),
};

export type Api = typeof api;
