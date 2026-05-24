# SuperTicket

**High-Velocity Ticketing & Hybrid AI Triage** — an enterprise-grade incident management platform with a FastAPI backend, SQLAlchemy ORM, and a web UI.

| | Details |
|---|---|
| **Version** | 0.1.0-beta.1 |
| **Python** | >=3.12 |
| **Package Manager** | uv (PEP 621) |
| **License** | — |

---

## Quick Start

```bash
# Clone and enter the project
git clone <repo-url> && cd superticket

# Install dependencies
uv sync

# Run Alembic migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn superticket.main:app --reload
```

The app will be available at [http://localhost:8000](http://localhost:8000). A default admin user is seeded on first startup:

| Email | Password |
|---|---|
| `admin@superticket.local` | `admin` |

### Configuration

Copy `.env.example` to `.env` and adjust values as needed. See [DESIGN.md — Configuration](DESIGN.md#9-configuration--environment) for the full list of variables.

```bash
cp .env.example .env
```

---

## What Is SuperTicket?

SuperTicket is an enterprise ticketing platform designed around two core ideas:

1. **High-Velocity Triage** — a strict state machine enforces linear progression (New → Triage → Assigned → In Progress → Pending Vendor → Resolved → Closed) with immutable audit logging on every transition.
2. **Hybrid AI Triage** — an LLM performs initial classification, sentiment analysis, PII scrubbing, and suggested resolution; a human dispatcher confirms or overrides the suggestion (planned for future releases).

### Implemented Features

- Full ticket CRUD via REST API (`/api/v1/tickets`)
- State machine with enforced transitions & audit logging
- User authentication (bcrypt + JWT) — login/register/profile endpoints
- Web UI: self-service portal, agent workspace, and admin user management
- Threaded comments on tickets (public & private)
- Knowledge base integration for agents

### Planned Features

See [DESIGN.md — Future Milestones](DESIGN.md#8-milestones).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI + Uvicorn |
| **ORM / Migrations** | SQLAlchemy 2.0 + Alembic |
| **Database** | SQLite (MVP) → PostgreSQL (future) |
| **Validation** | Pydantic v2 |
| **Auth** | bcrypt passwords, JWT tokens, session cookies |
| **Web UI** | Jinja2 templates + Starlette static files |
| **Package Manager** | uv |

---

## Running the Application

### Development

```bash
uv run uvicorn superticket.main:app --reload
```

The `--reload` flag enables auto-reload on file changes.

### Production

```bash
uv run uvicorn superticket.main:app --host 0.0.0.0 --port 8000
```

For production deployments, consider running Uvicorn behind a reverse proxy (e.g., Nginx) and switch the database to PostgreSQL via the `DATABASE_URL` environment variable.

---

## Testing

The project uses **pytest** with **pytest-asyncio**, **pytest-cov**, and **httpx**.

```bash
# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=superticket --cov-report=term-missing

# Specific test file
uv run pytest tests/test_state_machine.py -v
```

---

## Code Quality

**Ruff** is the configured linter and formatter.

```bash
# Check formatting and linting
uv run ruff check .

# Format code in place
uv run ruff format .
```

---

## Database Migrations

Alembic manages schema evolution. The migration history lives under `alembic/versions/`.

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description of change"

# Apply all pending migrations
uv run alembic upgrade head

# Roll back one migration
uv run alembic downgrade -1

# Show current revision
uv run alembic current
```

---

## Project Structure

```
superticket/
├── superticket/           # Main Python package
│   ├── main.py            # FastAPI app factory & lifespan events
│   ├── core/              # Configuration, exceptions, dependencies
│   ├── api/v1/            # REST API routers (tickets, auth, comments)
│   ├── views/             # Web UI route handlers (portal, agent, admin)
│   ├── schemas/           # Pydantic request/response DTOs
│   ├── services/          # Business logic & state machine
│   ├── models/            # SQLAlchemy ORM tables & enums
│   ├── db/                # Database engine & session setup
│   └── template_engine.py # Jinja2 rendering utilities
├── alembic/               # Alembic migration scripts
├── tests/                 # Test suite (201+ tests)
├── main.py                # Entry-point scaffold
├── SPECS.md               # System specification
└── DESIGN.md              # Architecture & design decisions
```

For detailed architecture, see [DESIGN.md](DESIGN.md). For the full system specification, see [SPECS.md](SPECS.md).

---

## API Documentation

When running, FastAPI auto-generates interactive docs at:

- **Swagger UI** — `http://localhost:8000/docs`
- **ReDoc** — `http://localhost:8000/redoc`

The OpenAPI schema is also available as JSON at `/openapi.json`.

---

## Contributing

1. Fork the repository and create a feature branch from `main`.
2. Write tests for new functionality (see AGENTS.md testing policy).
3. Ensure `ruff check .` and `uv run pytest` pass before committing.
4. Submit a pull request with a summary of changes.

---

## Versioning

Semantic versioning with stage suffixes:

| Stage | Format | Example |
|---|---|---|
| Alpha | `x.x.x-alpha.N` | `0.1.0-alpha.3` |
| Beta | `x.x.x-beta.N` | `0.1.0-beta.1` |
| Release | `x.x.x` | `0.1.0` |
