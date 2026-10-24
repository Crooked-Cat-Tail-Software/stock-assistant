# Product Spec — Stock Research Assistant

## Problem

Retail investors who want a quick read on a stock have to jump between quote
sites, charting tools, and news feeds, then piece the answer together
themselves. Questions like "How has NVDA moved this week compared with AMD?"
or "What were today's top gainers?" need several lookups and manual
comparison.

## Solution

A web app where the user asks market questions in plain English. An AI agent
answers them using live market data: quotes, price history, and news
headlines from Yahoo Finance (the yfinance library and Yahoo's RSS headline
feed), and top movers and fundamentals from Alpha Vantage's MCP server, which
is also the fallback whenever Yahoo fails.
Conversations are saved so the user can return to them. The user also keeps a watchlist of tickers they care about,
and can start a conversation about a watchlist ticker in one click.

## Users

A single investor using the app for personal research. This is a class
project, so there are no multi-user accounts.

## Core features

| ID | Feature | Expected behavior |
|----|---------|-------------------|
| F1 | Ask a question | User types a question in a chat. The agent calls market-data tools as needed (Yahoo for quotes, history, and news; Alpha Vantage for the rest and as fallback) and replies in under ~30 s. The UI shows which tools were used. |
| F2 | Conversation history | Every chat is a *session*. Sessions are listed newest first with a title (the first question, trimmed) and can be reopened with full history. The agent remembers earlier turns in the same session. |
| F3 | Delete a session | User can delete a session; it disappears from the list and its messages are removed. |
| F4 | Watchlist | User can add a ticker (1–10 letters with an optional class suffix such as `BRK.B`, stored uppercase) with an optional note, view the list, and remove tickers. Duplicate tickers are rejected. |
| F5 | Ask about a watchlist ticker | One click starts a new session with a prefilled question about that ticker. |
| F6 | Health check | `GET /api/health` reports whether the API and database are up, for deploy checks and monitoring. |

## Non-goals

- User accounts, sign-up, or login
- Trading, order placement, or brokerage integration
- Personalized investment advice. The agent states that its answers are
  informational only.
- Streaming token-by-token responses. Replies arrive whole; streaming may be
  added later.

## Guardrails (also see `security/`)

- **Cost protection:** questions are capped at 2,000 characters, and requests
  are rate-limited per client IP (HTTP 429 when exceeded). This stops a public
  URL from running up the OpenAI bill.
- **Read-only market-data tools only:** the agent has three Yahoo tools
  (`get_quote`, `get_price_history`, `get_news`) and the Alpha Vantage MCP
  server. Symbols are validated before any request, every Yahoo call has a
  timeout, the news feed is size-capped and parsed with `defusedxml`, and only
  https links are passed on.
- **Third-party text is data:** news headlines and summaries come from
  outside sources and go to the model. The agent is instructed to report them
  but never follow instructions inside any tool result (prompt injection).
- **No local tool access:** no filesystem, shell, or other local-access tools.
  The example's `filesystem` MCP server is deliberately left out because it
  would let a prompt read server files such as `.env`.
- **Secrets stay server-side:** `OPENAI_API_KEY` and `ALPHAVANTAGE_API_KEY`
  live only in backend environment variables and never reach the browser or
  the logs.
- **External limits:** the Alpha Vantage free tier allows roughly 25 requests
  per day, so quotes, price history, and news come from Yahoo Finance first
  (no key; cached for 60 s, 15 min, and 10 min), keeping Alpha Vantage for
  movers, fundamentals, and fallback. When a source fails or is exhausted, the agent
  says so instead of guessing. Automated tests never call OpenAI, Alpha
  Vantage, or Yahoo.
- **Yahoo Finance terms:** yfinance is an unofficial library that reads Yahoo
  Finance data, which Yahoo intends for personal and educational use. That
  fits this class project, but a commercial product would need a licensed
  data provider.

## Acceptance criteria

1. A new user can run `docker compose up`, open the app, ask "What is AAPL's
   latest price?", and get an answer that names the tool it used, such as
   `get_quote` (real agent) or `GLOBAL_QUOTE` (Alpha Vantage fallback, and the
   keyless fake agent).
2. After a page refresh or container restart, the session and its messages
   are still listed.
3. Adding `aapl` to the watchlist stores `AAPL`; adding it again returns 409.
4. A 2,001-character question is rejected with 422 and a clear message.
5. All behavior above is covered by integration tests that run in CI without
   real OpenAI, Alpha Vantage, or Yahoo access.
