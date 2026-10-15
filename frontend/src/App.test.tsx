import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./api/ApiContext";
import { ApiError, type Api } from "./api/client";
import App from "./App";
import { watchlistPrompt } from "./lib/validation";
import { createFakeApi, sessionFixture } from "./test/fakeApi";

function renderApp(api: Api = createFakeApi()) {
  render(
    <ApiProvider api={api}>
      <App />
    </ApiProvider>,
  );
  return { api, user: userEvent.setup() };
}

const questionBox = () => screen.getByRole("textbox", { name: "Your question" });
const sidebar = () => screen.getByRole("navigation", { name: "Conversations" });

describe("asking questions", () => {
  it("creates a session on the first question and shows the answer with its data source", async () => {
    const { api, user } = renderApp();

    await user.type(questionBox(), "What is AAPL's latest price?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    const answer = await screen.findByRole("article", { name: "Assistant" });
    expect(answer).toHaveTextContent("AAPL is at $123.45.");
    expect(within(answer).getByRole("list", { name: "Data sources used" })).toHaveTextContent("GLOBAL_QUOTE · AAPL");
    expect(api.createSession).toHaveBeenCalledTimes(1);
    expect(questionBox()).toHaveValue("");
    expect(await within(sidebar()).findByText("What is AAPL's latest price?")).toBeInTheDocument();
  });

  it("reuses the same session for follow-up questions", async () => {
    const { api, user } = renderApp();

    await user.type(questionBox(), "first{Enter}");
    await screen.findByText("Here is your answer.");
    await user.type(questionBox(), "second{Enter}");

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledTimes(2));
    expect(api.createSession).toHaveBeenCalledTimes(1);
    const [firstId] = vi.mocked(api.sendMessage).mock.calls[0];
    expect(vi.mocked(api.sendMessage).mock.calls[1][0]).toBe(firstId);
  });

  it("Shift+Enter adds a new line instead of sending", async () => {
    const { api, user } = renderApp();
    await user.type(questionBox(), "line one{Shift>}{Enter}{/Shift}line two");
    expect(questionBox()).toHaveValue("line one\nline two");
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("blocks questions over 2,000 characters", async () => {
    const { user } = renderApp();
    await user.click(questionBox());
    await user.paste("x".repeat(2001));
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("shows the error, keeps the question, and removes the unsent message when the agent fails", async () => {
    const api = createFakeApi();
    vi.mocked(api.sendMessage).mockRejectedValueOnce(
      new ApiError(502, "upstream_error", "The market data service is unavailable."),
    );
    const { user } = renderApp(api);

    await user.type(questionBox(), "What is AAPL?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("The market data service is unavailable.");
    expect(questionBox()).toHaveValue("What is AAPL?");
    expect(screen.queryByRole("article", { name: "You" })).not.toBeInTheDocument();
  });
});

describe("conversation history", () => {
  it("opens a saved conversation and shows its messages", async () => {
    const { user } = renderApp(createFakeApi({ sessions: [sessionFixture()] }));

    await user.click(await within(sidebar()).findByRole("button", { name: /^How is MSFT doing\?/ }));

    expect(await screen.findByText("MSFT closed at $400.")).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "You" })).toHaveTextContent("How is MSFT doing?");
  });

  it("deletes a conversation after confirmation, and keeps it when cancelled", async () => {
    const { api, user } = renderApp(createFakeApi({ sessions: [sessionFixture()] }));
    const deleteButton = await screen.findByRole("button", { name: /Delete conversation/ });

    vi.spyOn(window, "confirm").mockReturnValueOnce(false);
    await user.click(deleteButton);
    expect(api.deleteSession).not.toHaveBeenCalled();

    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    await user.click(deleteButton);
    await waitFor(() => expect(within(sidebar()).getByText("No conversations yet.")).toBeInTheDocument());
  });
});

describe("watchlist", () => {
  it("adds a ticker in uppercase and removes it", async () => {
    const { user } = renderApp();

    await user.type(screen.getByRole("textbox", { name: "Ticker symbol" }), "nvda");
    await user.type(screen.getByRole("textbox", { name: "Note (optional)" }), "AI chips");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("AI chips")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove NVDA" }));
    await waitFor(() => expect(screen.queryByText("NVDA")).not.toBeInTheDocument());
  });

  it("explains invalid tickers without calling the backend", async () => {
    const { api, user } = renderApp();
    await user.type(screen.getByRole("textbox", { name: "Ticker symbol" }), "123{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Use 1–10 letters");
    expect(api.addWatchlistItem).not.toHaveBeenCalled();
  });

  it("shows the backend's message for duplicates", async () => {
    const { user } = renderApp(
      createFakeApi({ watchlist: [{ symbol: "AAPL", note: null, created_at: "2026-10-15T00:00:00Z" }] }),
    );
    await screen.findByText("AAPL");

    await user.type(screen.getByRole("textbox", { name: "Ticker symbol" }), "aapl{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("AAPL is already on the watchlist");
  });

  it("Ask prefills a question in a new chat without sending it", async () => {
    const { api, user } = renderApp(
      createFakeApi({ watchlist: [{ symbol: "TSLA", note: null, created_at: "2026-10-15T00:00:00Z" }] }),
    );

    await user.click(await screen.findByRole("button", { name: "Ask about TSLA" }));

    expect(questionBox()).toHaveValue(watchlistPrompt("TSLA"));
    expect(api.sendMessage).not.toHaveBeenCalled();
  });
});

describe("load failures", () => {
  it("explains when conversations can't be loaded", async () => {
    const api = createFakeApi();
    vi.mocked(api.listSessions).mockRejectedValue(new ApiError(503, "http_error", "The service is temporarily unavailable."));
    renderApp(api);
    expect(await within(sidebar()).findByRole("alert")).toHaveTextContent("The service is temporarily unavailable.");
  });
});

describe("health badge", () => {
  it("shows when the backend is unreachable", async () => {
    const api = createFakeApi();
    vi.mocked(api.getHealth).mockRejectedValue(new ApiError(0, "network_error", "down"));
    renderApp(api);
    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
  });
});
