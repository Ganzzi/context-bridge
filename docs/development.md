# Development Guide

## Prerequisites
- Python 3.11+
- `uv`
- Docker and Docker Compose
- PostgreSQL and Ollama available locally (the provided `docker-compose.yml` starts both)

## Setup
```bash
uv sync --all-groups --all-extras
cp .env.example .env
```

## Local Services
Start the local dependencies defined in `docker-compose.yml`:

```bash
docker compose up -d postgres ollama
```

Default local endpoints:
- PostgreSQL: `localhost:5432`
- Ollama: `http://localhost:11434`

## Database Initialization
Initialize or verify the database schema:

```bash
uv run python -m context_bridge.database.init_databases init
uv run python -m context_bridge.database.init_databases verify
```

## Unit Tests (PR Gate)
```bash
uv run pytest -m "not integration and not e2e" -q
```

## Integration / E2E Tests
```bash
uv run pytest -q
uv run pytest -m integration
uv run pytest -m e2e
```

## Coverage
```bash
uv run pytest -m "not integration and not e2e" --cov=context_bridge --cov-report=term-missing
```

## Code Quality
```bash
uv run black --check context_bridge/
uv run ruff check context_bridge/
uv run mypy context_bridge/
```

## Streamlit UI
Run the local UI:

```bash
uv run streamlit run streamlit_app/app.py
```

## MCP Server
Run the MCP server locally:

```bash
uv run python -m context_bridge_mcp
```

## CI Behavior
- Pull requests and pushes run the PR-gated Python test command: `uv run pytest -m "not integration and not e2e" -q`
- CI also runs Black, Ruff, and mypy from `.github/workflows/tests.yml`
- Release automation runs when a version tag is pushed

## Known Issues
- The repository currently has substantial in-progress local changes; keep cleanup commits narrowly scoped.
- Some historical test/demo scripts still live under `scripts/` and are not part of the main pytest suite.
