# Book Illustration Studio

A web application that transforms book text into character portraits and chapter illustrations using Google's Gemini API.

## Architecture

- **Frontend**: Next.js + TypeScript
- **Backend**: FastAPI + Python
- **Storage**: JSON files + local filesystem
- **API**: REST with polling for progress updates
- **AI**: Google GenAI Python SDK

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Gemini API key (free tier is enough for the text pipeline; image models are paid-only — see [DECISIONS.md](DECISIONS.md))

### Setup

1. **Install dependencies:**
   ```bash
   make setup
   # Or individually:
   make install-backend
   make install-frontend
   ```

2. **Configure environment:**
   ```bash
   # Copy .env.example to backend/.env and add your Gemini API key
   cp .env.example backend/.env
   # Edit backend/.env and add your GEMINI_API_KEY
   
   # Create frontend environment file
   cp frontend/env.local.example frontend/.env.local
   ```

3. **Start the application:**
   ```bash
   # Start both frontend and backend
   make dev

   # Or start individually:
   make dev-backend  # Terminal 1
   make dev-frontend # Terminal 2
   ```

### Image Generation

Image generation uses **mock** mode by default - local placeholder images, zero API cost. This is because every current Gemini image model is paid-only (no free tier), so the app works out of the box; the text pipeline (style, characters, chapters) always uses real Gemini calls with the free tier.

To switch providers, set `IMAGE_PROVIDER` in `backend/.env`:
```bash
IMAGE_PROVIDER=mock   # Default - local placeholder images, no cost
IMAGE_PROVIDER=gemini # Real Gemini Nano Banana calls (billing required)
```

`IMAGE_PROVIDER=gemini` uses `gemini-3.1-flash-lite-image` via the same notebook-faithful pipeline (context-seeded, interaction-chained) so characters stay consistent across portraits and illustrations.

### Run Tests

```bash
# Run all tests
make test

# Or run individually:
make test-backend
make test-frontend
```

## Project Structure

```
gradion/
├── frontend/          # Next.js frontend
│   ├── app/          # Next.js app directory
│   ├── components/   # React components
│   └── lib/          # Utilities and API clients
├── backend/          # FastAPI backend
│   ├── app/          # Application modules
│   │   ├── api/      # API routes
│   │   ├── models/   # Pydantic models
│   │   └── services/ # Business logic
│   └── tests/       # Backend tests
├── data/            # JSON file storage
│   ├── users/       # User data
│   ├── projects/    # Project data
│   ├── files/       # Book texts and images
│   └── locks/       # Write locks
├── README.md
├── DECISIONS.md     # Technical decisions
└── .env.example     # Environment variables template
```

## API Endpoints

- `GET /api/health` - Health check endpoint
- `POST /api/auth/sign-in` - User authentication
- `GET /api/projects` - List user projects
- `POST /api/projects` - Create new project
- `GET /api/projects/:id` - Get project details
- `POST /api/projects/:id/steps/:step` - Execute pipeline step
- `GET /api/projects/:id/status` - Get project status
- `POST /api/projects/:id/steps/:step/retry` - Retry failed step

## Pipeline Steps

1. **Style** - Generate or define art style
2. **Characters** - Extract adult characters with prompts
3. **Portraits** - Generate character images
4. **Chapters** - Generate chapter illustration prompts
5. **Illustrations** - Generate scene illustrations

## Development

The application follows a phased development approach:

- **Phase 1**: Project setup, basic frontend/backend, health checks
- **Phase 2**: Authentication and project management
- **Phase 3**: Gemini pipeline integration
- **Phase 4**: Frontend UI implementation
- **Phase 5**: Testing and documentation

## License

Internal assessment project - Gradion