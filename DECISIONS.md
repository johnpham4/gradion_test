# Decisions

This document records important technical decisions,
alternatives considered, and cases where AI-generated
suggestions were overridden.

## FastAPI over Express for Backend

My decision to use FastAPI instead of Express was driven by the Python-based Gemini cookbook. The Google Genai SDK (`google-genai>=2.10.0`) used in the reference notebook is Python-native, which significantly reduces integration complexity. FastAPI's async support is critical for handling long-running Gemini calls (10-30s+) without blocking the event loop, and its native Pydantic integration aligns perfectly with the structured output requirements. The trade-off is a Python/JavaScript language split between frontend and backend, but the reliability benefits outweigh this.

**AI suggestion:** Claude initially suggested Express.js for better JavaScript ecosystem alignment. I pushed back because the integration complexity with Gemini's Python SDK would introduce unnecessary risk in a 16-hour timeline.

## JSON File Storage over Database

I chose JSON file storage with file-based write locking instead of a traditional database. For the single-user assessment scope, a full database adds overhead without meaningful benefits. JSON files provide sufficient persistence, are easier to debug, and eliminate external dependencies. The cons accepted include manual write locking implementation and no query capabilities. The state isolation per user/project is handled through directory structure, and concurrent writes are prevented using fcntl-based file locking.

**AI suggestion:** AI recommended PostgreSQL for robustness and future scalability. I overrode this because the assessment specifically allows JSON storage "if done properly," and a database would be over-engineering for this scope.

## Polling over WebSockets

I chose simple HTTP polling for pipeline progress updates instead of WebSockets. Real-time updates are listed as a bonus feature, not a requirement. Polling is simpler to implement, sufficient for the assessment scope, and avoids the complexity of WebSocket connection management. The frontend will poll the status endpoint every 2-3 seconds during step execution.

**AI suggestion:** AI suggested WebSockets for better user experience. I pushed back because the implementation complexity isn't justified for the basic requirements, and polling meets the spec's needs.

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

---

## If I had one more day

If I had one more day, I would implement real-time step updates using Server-Sent Events (SSE) instead of polling. SSE provides a middle ground between polling's simplicity and WebSockets' complexity - it's HTTP-based, unidirectional (server to client), and much simpler to implement than WebSockets while still providing instant updates. This would significantly improve the user experience during the long-running image generation steps without adding the complexity of bidirectional WebSocket connections.