# Testing

## Strategy

Tests focus on the logic that would actually break: step ordering, progress
persistence, retry/stranded recovery, the no-duplicate-call guard, and the
server-side caps (2 characters / 1 chapter). Frontend tests cover the two
states that matter most for the demo — sign-in and the project list — rather
than testing every component exhaustively.

## Backend (pytest)

`make test-backend` runs `pytest` from `backend/`. Without `make`, from `backend/`:
`venv/Scripts/python -m pytest` (Windows) or `venv/bin/python -m pytest` (Unix).

What we test:

- **Identity & projects** — sign-in (new/existing/invalid), sign-out, project
  create (paste + `.txt` upload + validation), project isolation between
  users, book text round-trip. (`tests/test_auth.py`, `tests/test_projects.py`)
- **Pipeline behavior** — initial state, multi-step state persistence,
  step-ordering enforcement (a step cannot run before the previous one),
  atomic RUNNING transition (the no-duplicate-call guard), completed/failed
  transitions, results preserved across later steps and retries, stranded-step
  detection and recovery, state persistence across a simulated reload, and a
  full 5-step run with mocked Gemini. (`tests/test_pipeline.py`)
- **Server-side caps** — characters capped at 2, chapters at 1, portraits at 2,
  illustrations at 1, enforced inside the pipeline, not just in the UI.
- **Step results** — `StepState.result` round-trips style, characters, chapters,
  portraits, illustrations, and error cases. (`tests/test_step_results.py`)
- **Image providers** — `MockImageClient` init/output, aspect ratios, cleanup,
  and provider selection from config. (`tests/test_image_providers.py`)

What we deliberately do **not** test:

- Real Gemini calls (they cost money and are non-deterministic) — the Gemini
  client is mocked. The live path is exercised manually against the real API.
- The `GeminiClient` HTTP layer itself — it is a thin wrapper around the
  official SDK; testing it would test Google's SDK, not our logic.
- Multi-process concurrency — the app runs as a single uvicorn worker and the
  no-duplicate-call guard relies on an in-process reentrant lock, so the tests
  cover the concurrent-trigger case at the thread level.

### Backend test report (real run, 2026-08-13)

```
$ pytest -q
collected 63 items

tests\test_auth.py .......                                       [ 11%]
tests\test_health.py ..                                          [ 14%]
tests\test_image_providers.py ......                             [ 23%]
tests\test_pipeline.py ............................               [ 68%]
tests\test_projects.py .............                             [ 88%]
tests\test_step_results.py .......                               [100%]

======================= 63 passed, 8 warnings in 3.41s ========================
```

The 8 warnings are starlette `DeprecationWarning`s about per-request cookies in
`TestClient` — cosmetic, non-fatal.

## Frontend (jest)

`make test-frontend` runs `npm test -- --watchAll=false` from `frontend/`. Without `make`, from `frontend/`: `npm test -- --watchAll=false`.

What we test:

- **Sign-in** — renders the form, validates input, calls the API on submit,
  shows errors. (`app/__tests__/sign-in.test.tsx`)
- **Project list** — renders projects, shows title/date/status, handles the
  empty state, renders the progress indicator across the 5 steps.
  (`app/__tests__/project-list.test.tsx`)

What we deliberately do **not** test:

- `ProjectDetail` step execution — it drives real polling and long-running
  steps; asserting its in-flight transitions would mean mocking timers heavily.
  Its behavior is verified through the manual end-to-end run below.
- Styling/layout — Tailwind classes are not meaningful to assert.

### Frontend test report (real run, 2026-08-13)

```
$ npm test -- --watchAll=false

PASS app/__tests__/sign-in.test.tsx (8.428 s)
PASS app/__tests__/project-list.test.tsx (8.506 s)

Test Suites: 2 passed, 2 total
Tests:       9 passed, 9 total
Time:        26.13 s
```

## Manual end-to-end (not automated, no real-image quota)

The happy path is exercised by hand against a running stack with a real Gemini
text key and the mock image provider:

1. Sign in with email + name.
2. Create a project from pasted book text.
3. Run STYLE (real Gemini text, optional user style) → style text appears under
   the step.
4. Run CHARACTERS → 2 character cards with prompts.
5. Run PORTRAITS → 2 portrait images, served through `/api/images/...`.
6. Run CHAPTERS → 1 chapter card.
7. Run ILLUSTRATIONS → 1 scene image.
8. Refresh mid-pipeline → project reopens at the correct step with all results
   intact; images are served only to the authenticated user.

The image model itself is paid-only (no free tier as of 2026), so automated
tests use `MockImageClient`; real image generation is available by setting
`IMAGE_PROVIDER=gemini`.
