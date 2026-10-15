import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

function mockFetch(response: Response | Error) {
  const fn = vi.fn(async () => {
    if (response instanceof Error) throw response;
    return response;
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("returns parsed JSON on success", async () => {
    mockFetch(json([{ symbol: "AAPL", note: null, created_at: "2026-10-15T00:00:00Z" }]));
    await expect(api.listWatchlist()).resolves.toEqual([
      { symbol: "AAPL", note: null, created_at: "2026-10-15T00:00:00Z" },
    ]);
  });

  it("sends JSON bodies with the right method, path, and header", async () => {
    const fetchFn = mockFetch(json({ user_message: {}, assistant_message: {} }));
    await api.sendMessage("abc", "What is AAPL?");
    expect(fetchFn).toHaveBeenCalledWith("/api/sessions/abc/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "What is AAPL?" }),
    });
  });

  it("encodes path parameters", async () => {
    const fetchFn = mockFetch(new Response(null, { status: 204 }));
    await api.removeWatchlistItem("BRK.B/../x");
    expect(fetchFn.mock.calls[0]).toEqual([
      "/api/watchlist/BRK.B%2F..%2Fx",
      expect.objectContaining({ method: "DELETE" }),
    ]);
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(api.deleteSession("abc")).resolves.toBeUndefined();
  });

  it("turns contract error bodies into ApiError with code and message", async () => {
    mockFetch(json({ code: "duplicate_symbol", message: "AAPL is already on the watchlist" }, 409));
    const error = await api.addWatchlistItem({ symbol: "AAPL" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "duplicate_symbol", message: "AAPL is already on the watchlist" });
  });

  it("uses a friendly fallback when a proxy returns a non-JSON error", async () => {
    mockFetch(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(api.listSessions()).rejects.toMatchObject({
      status: 502,
      code: "http_error",
      message: "The assistant's data service failed. Please try again.",
    });
  });

  it("reports network failures as status 0", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    await expect(api.getHealth()).rejects.toMatchObject({ status: 0, code: "network_error" });
  });
});
