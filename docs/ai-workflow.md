# AI-assisted development workflow

How AI tools were used to build this project: what was delegated, which
context files guided the AI, what was reviewed by hand, and how each step was
verified.

## Tools and context files

- **Claude Code** (desktop app): planning, scaffolding, code generation
- **Context files:** `AGENTS.md` (rules for any AI agent; `CLAUDE.md` imports
  it), `product-spec.md`, and `openapi.yaml`

## Log

### 2026-10-15 — Project selection and Phase 1 (spec and contract)

**Asked:** Could the Alpha Vantage MCP agent example be adapted to meet the
course project requirements?

**AI did:**
- Compared the example (a CLI-only Python agent) with the 14 rubric criteria
  and estimated that, as-is, it would score about 4–6 of 30
- Reviewed my existing `stock-market-analytics` repo as an alternative base and
  rejected it (notebooks for a different course, with no web components)
- Read the example's source and found three design issues: an unsafe
  `filesystem` MCP server, built-in SQLite session storage, and an MCP
  connection tied to the CLI's lifetime
- Drafted `product-spec.md`, `openapi.yaml`, and `AGENTS.md`

**My decisions:** OpenAI as the AI provider, Render or Railway for
deployment, and a new repo rather than reusing the old one.

**Verified:**
- `uvx openapi-spec-validator openapi.yaml` → OK
- Diffed `THIRD_PARTY_NOTICES.md` against the upstream MIT `LICENSE` → identical
- Caught and fixed a mismatch between the spec and the contract (the spec said
  tickers were "uppercase", while the contract accepts lowercase and
  uppercases it)

**Reviewed by hand:** _TODO (me): read through the spec and contract and note
any changes here._
