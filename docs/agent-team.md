# Agent team

This project is built by a human working with AI coding agents. This page
defines who does what, what each role may and may not do, and how work moves
between them. The workflow steps are in [process.md](process.md).

## Roles

| Role | Who | Responsible for | May | Must not |
|------|-----|-----------------|-----|----------|
| **Product owner & reviewer** | Human (project author) | Scope and priorities, choices between options (providers, hosting, cost), accepting or rejecting work, merging PRs, everything that needs an account or a secret | Everything | — |
| **Lead agent** | Claude Code (main session) | Turning issues into plans, implementing, running tests, keeping docs and the AI workflow log current, updating issues, coordinating specialists | Edit code and docs, run commands, open branches, PRs, and issues, push to branches | Handle secret values; change account settings (Render, GitHub secrets) without the human; merge to `main` without approval |
| **Contract reviewer** | Subagent [`contract-reviewer`](../.claude/agents/contract-reviewer.md) | Finding drift between `openapi.yaml`, the backend, and the frontend types | Read, search, run validators and tests | Edit files |
| **Test engineer** | Subagent [`test-engineer`](../.claude/agents/test-engineer.md) | Choosing the right test layer, writing tests, and proving each new test can fail | Edit test files only, run tests | Change production code; call real external APIs |
| **Security reviewer** | Subagent [`security-reviewer`](../.claude/agents/security-reviewer.md) | Secrets, logging, guardrails (rate limit, internal token, CSP), and agent tool scope | Read, search, run scanners (gitleaks, ruff `S`, npm audit) | Edit files; print secret values |
| **Deploy verifier** | Subagent [`deploy-verifier`](../.claude/agents/deploy-verifier.md) | Checking production after a deploy and diagnosing the live site | Read-only HTTP checks against production | Change code or settings; send real questions (they cost money) unless asked |
| **CI gatekeeper** | GitHub Actions [`ci.yml`](../.github/workflows/ci.yml) | Running every check on each push and PR | — | — |
| **Deployer** | Render (`autoDeployTrigger: checksPass`) | Deploying `main` only after all CI checks pass | — | — |
| **Production check** | GitHub Actions [`verify-deploy.yml`](../.github/workflows/verify-deploy.yml) | Confirming both services run the deployed commit and smoke-testing the live site | — | — |
| **Runtime agent** (part of the product) | OpenAI Agents SDK in `backend/app/agent/` | Answering users' market questions with yfinance tools (quotes, history) and Alpha Vantage MCP tools | Call Alpha Vantage tools only | Use filesystem, shell, or other local-access tools |

The subagents are real Claude Code subagent definitions. Their tool lists
enforce the "may / must not" columns: reviewers have no edit tools.

## How they work together

```
 Human ──creates/prioritizes──▶ GitHub issue (acceptance criteria)
                                   │
                                   ▼
                         Lead agent comments a plan on the issue
                                   │ (human objects or adjusts, if needed)
                                   ▼
                    Lead agent implements on a branch
                    (contract first: openapi.yaml → backend → frontend types)
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
 contract-reviewer          test-engineer              security-reviewer
 (API changed?)             (every change)             (config, deploy, logging,
                                                        auth, or agent tools changed?)
        └──────────────┬───────────┴──────────────────────────┘
                       ▼  findings fixed by the lead agent
              Pull request "Closes #N" ──▶ CI gatekeeper (5 checks)
                       │
                       ▼
              Human reviews and merges
                       │
                       ▼
              Render deploys (only if CI passed) ──▶ verify-deploy workflow
                       │
                       ▼
              deploy-verifier on request / when something looks wrong
                       │
                       ▼
              Issue closed with links to the commit, tests, and evidence
```

**Hand-off rules**

- Every piece of work starts from an issue with acceptance criteria. The lead
  agent posts its plan as a comment before starting, and a summary of the
  evidence (tests, commands, links) when done.
- Specialists report back to the lead agent. They don't fix things themselves
  (except the test engineer, for tests). The lead agent applies fixes, and the
  human decides on disagreements.
- Anything involving an account, a secret, money, or public posting goes back
  to the human. Examples from this project: choosing Neon over Render
  Postgres, entering keys in Render, making the repo public.
- When an agent finds that a document or plan is wrong (for example, the
  changed course criteria, or Render's real URL differing from the guessed
  one), it stops, reports, and updates the doc before continuing.

## How it has actually worked so far

Being honest about history, because the log is graded too:

- **Phases 1–7** (see [ai-workflow.md](ai-workflow.md)) were done by the human
  and **one lead agent**. The lead agent did the specialist roles itself:
  contract checks through `test_contract_coverage.py` and `assert_conforms`,
  test design with deliberate "break it to prove it fails" checks, security
  passes (gitleaks before publishing, key-leak tests), and production
  verification (the rate-limit investigation).
- The human made every scope, cost, and account decision, and did every step
  that needed a dashboard or a secret.
- The specialist subagents above formalize those roles from this point on,
  with tool limits that match what each role did. The public tracker
  (GitHub Issues) starts with the same change: earlier work is recorded there
  as issues labeled `recorded-after-the-fact`.
