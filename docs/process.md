# Development process

How a change goes from idea to production. Who does each step is in
[agent-team.md](agent-team.md).

## 1. Track it

All work starts as a **GitHub issue** in the public tracker:
<https://github.com/Crooked-Cat-Tail-Software/stock-assistant/issues>

- The title says the outcome ("Single command to run all tests"), not the
  activity.
- The body has **acceptance criteria** as a checklist. Each item must be
  checkable: a command, a status code, or a visible behavior.
- Labels: `feature` (user-facing, from `product-spec.md`), `infrastructure`,
  `documentation`, `agent-process`, `bug`. `recorded-after-the-fact` marks
  issues added later for work done before the tracker existed.
- A new **feature** first goes into `product-spec.md` (the Fn table and the
  acceptance criteria), then gets an issue.

## 2. Plan it

Before writing code, the lead agent **comments its plan on the issue**: the
approach, files to change, how it will be verified, and any open questions.
The human adjusts the plan or answers the questions there or in chat.

## 3. Build it on a branch

- Branch from `main`: `<topic>/<short-name>` (e.g. `quick-wins/agent-process`).
- **Contract first** for any API change: `openapi.yaml` → validate → backend →
  `npm run gen:api` → frontend → tests.
- **Schema changes** need an Alembic migration
  (`uv run alembic revision --autogenerate`). Review the generated file.
- Commit in small, reviewable steps. Reference the issue in the commit
  message (`Refs #N`) and end with the AI co-author trailer.
- Add an entry to [ai-workflow.md](ai-workflow.md) for meaningful AI-assisted
  work: what was asked, what the AI did, problems found, how it was verified,
  and what the human reviewed.

## 4. Review it

Run the specialists that apply (see [agent-team.md](agent-team.md)):

| Changed… | Run |
|----------|-----|
| An endpoint, request, or response | `contract-reviewer` |
| Any behavior | `test-engineer` (new tests must be shown to fail without the change) |
| Config, deployment, nginx, logging, auth, or the agent's tools | `security-reviewer` |

The lead agent fixes the findings, and the human settles disagreements.

## 5. Open a pull request

- The body lists what changed, how it was verified, and `Closes #N` for each
  issue it finishes.
- **CI must pass** (`.github/workflows/ci.yml`): contract, backend (unit +
  integration on Postgres), frontend (lint, typecheck, unit, build), end-to-end,
  Docker Compose smoke test, and production-image smoke test.
- **The human reviews and merges.** Agents don't merge to `main`.

## 6. Deploy and verify

- Merging to `main` re-runs CI. **Render deploys only if every check passes**
  (`autoDeployTrigger: checksPass`).
- `verify-deploy.yml` then confirms the site runs the merged commit and
  smoke-tests production.
- For anything user-visible, the `deploy-verifier` subagent checks the live
  site.
- **Exception:** changes to `render.yaml` are applied by Render's Blueprint
  sync immediately, without waiting for CI (see
  [deployment.md](deployment.md#known-gap-renderyaml-changes-skip-the-ci-gate)).
  Commit them on their own, never mixed with code.

## Definition of done

An issue is closed when **all** of these hold:

- [ ] Every acceptance criterion is checked, with evidence in a closing
      comment or the PR: commands run, test names, status codes, links
- [ ] `make test` passes locally, and all CI checks pass on the PR
- [ ] New tests were shown to fail without the change
- [ ] Docs affected by the change are updated (README, AGENTS.md, `docs/`)
- [ ] The AI workflow log has an entry, with "Reviewed by hand" completed by
      the human
- [ ] For deployed changes: production verified (verify-deploy passed)
