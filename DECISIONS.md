# Decisions

This document records important technical decisions,
alternatives considered, and cases where AI-generated
suggestions were overridden.

## FastAPI over Express for Backend

My decision to use FastAPI instead of Express was driven by the Python-based Gemini cookbook. The Google Genai SDK (`google-genai>=2.10.0`) used in the reference notebook is Python-native, which significantly reduces integration complexity. FastAPI's async support is critical for handling long-running Gemini calls (10-30s+) without blocking the event loop, and its native Pydantic integration aligns perfectly with the structured output requirements. The trade-off is a Python/JavaScript language split between frontend and backend, but the reliability benefits outweigh this.

**AI suggestion:** Claude initially suggested Express.js for better JavaScript ecosystem alignment. I pushed back because the integration complexity with Gemini's Python SDK would introduce unnecessary risk in a 16-hour timeline.

## JSON File Storage over Database

I chose JSON file storage instead of a traditional database. For the assessment scope, it's simple to prototype and the data stays human-readable for debugging. State is isolated per user/project through directory structure.

**AI suggestion:** AI recommended PostgreSQL for robustness and future scalability. I overrode this because the assessment explicitly allows JSON storage "if done properly," and a database would be over-engineering for this scope.

## Polling for Progress Updates

The frontend polls the project endpoint every 2-3 seconds while a step is running, so generated results appear as they land. Polling is simple, sufficient for the assessment scope, and works with the threadpool-based pipeline without any extra infrastructure.

**AI suggestion:** AI suggested a real-time transport for better user experience. I pushed back because the implementation complexity isn't justified for the basic requirements.

## Separate State Fields for Progress Tracking

I decided to use separate state fields (`overall_status` and `step_state`) instead of a single combined state. This separation allows expressing complex states like "step 3 completed, step 4 currently running" which a single enum cannot capture. The cost is keeping two fields synchronized and handling stranded step states with timeout detection.

**AI suggestion:** Claude proposed a single status enum with states like "STEP_3_RUNNING". I overrode this because it cannot properly represent the resumable state required by the spec - a refresh mid-step needs to show both progress and current execution.

## Chat Chaining for Book Context

I implemented Gemini's chat chaining (interaction IDs) to reuse book context across the 5 steps instead of re-sending the full book text each time. This follows the notebook's pattern exactly and provides significant cost savings. The book is uploaded once via File API, then each step chains from the previous interaction. The trade-off is dependency on interaction IDs, but this is managed through the project state.

**AI suggestion:** AI suggested re-sending book text with each call for simplicity. I pushed back because the assessment explicitly requires cost discipline - "Send the book's content to Gemini once and reuse it across steps."

## Makefile over Shell Scripts

I chose a Makefile instead of separate shell scripts for development commands. Make provides a unified interface for both Windows and Unix-like systems, better dependency management, and cleaner command organization. It handles the cross-platform differences better than maintaining separate .sh and .bat files.

**AI suggestion:** AI suggested separate shell scripts for simplicity. I overrode this because maintaining separate scripts for different platforms is error-prone, and Make provides a more professional development experience.

## pyproject.toml over requirements.txt

I chose pyproject.toml for Python dependency management instead of requirements.txt. This is the modern Python standard, provides better metadata management, and integrates well with setuptools for editable installs. It also allows defining development dependencies separately from production ones.

**AI suggestion:** AI suggested requirements.txt for simplicity. I pushed back because pyproject.toml is the modern standard and provides better project structure and dependency management.

## Gemini Image Generation: Paid-Only, So Mock Is the Default

The assessment requires "real calls to a current Gemini image model (Nano Banana family)" — §5.3 is explicit about it. However, as of 2026 **every current Gemini image model is paid-only**. The official pricing page (`ai.google.dev/gemini-api/docs/pricing`) lists `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite) as having **no free tier** (paid: $0.25 input / $30.00 per 1M output tokens → ~$0.034 per image); `gemini-2.5-flash-image` and the rest of the 2.5 family moved to paid-only in April 2026. Only the text model (`gemini-3.6-flash`) is free. I verified the text path works with a real key (live `interactions.create` returned "OK").

Decision: `IMAGE_PROVIDER=mock` is the **default** so the app runs out of the box at zero cost, with `IMAGE_PROVIDER=gemini` as a documented opt-in (billing required) that makes real Nano Banana calls using the exact notebook pipeline. The mock client (`MockImageClient`) keeps the identical interface (context seed + chained generations) and writes placeholder PNGs to `data/mock_images/`; real Gemini images are saved to `data/images/{project_id}/` via `_save_image`. If a free image tier appears later, flipping `IMAGE_PROVIDER=gemini` is all that's needed.

**AI suggestion:** The AI previously went mock-only and claimed image generation was unusable — and in that working-tree revision it silently stopped attaching the uploaded book to Gemini at all (STYLE never sent the book; CHARACTERS/CHAPTERS re-sent `book_text[:5000]` every step instead of chaining). I caught that regression by reading the diff, restored the notebook's interactions-chaining pipeline, and kept the mock client only as an explicit fallback. The real integration remains the deliverable; the mock is the safety net, not a replacement for the chaining logic.

## Each Step Returns Its Result on Completion

The user asked whether each step should return its result when run. Yes — every step writes its output to `step_states[STEP].result` as soon as it's produced (style string, character/chapter arrays, portrait/illustration objects with file paths), and `trigger_step`/`retry_step` return the final `{status, result}`. During execution the frontend polls `/projects/{id}` and renders each step's result under that step (including partial portrait/illustration lists while the rest are still generating). To keep the event loop free during long Gemini calls, `trigger_step`/`retry_step` are declared as sync handlers so FastAPI runs them in a threadpool — otherwise the 10-30s synchronous Gemini call would block the loop and freeze the status polls the UI depends on.

---

## If I had one more day

If I had one more day, I would implement real-time step updates using Server-Sent Events (SSE) instead of polling. SSE is HTTP-based and unidirectional (server to client), which would make generated results appear instantly during the long image-generation steps without the polling delay.