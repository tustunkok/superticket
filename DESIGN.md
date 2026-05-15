# SuperTicket — High-Level Architectural Design

## Document Status
This is a living document. As the project evolves, this file will be updated to reflect the current and target architecture.

---

## 1. Framework Decision

**Chosen: FastAPI + SQLAlchemy**

Rationale: While Django provides a full-featured admin interface and ORM out of the box, FastAPI is the better fit for this project for the following reasons:

1. **API-First Alignment**: FastAPI is purpose-built for REST APIs, with automatic interactive documentation (Swagger UI, ReDoc) and native Pydantic integration. Since our MVP target is API-first, FastAPI reduces friction.
2. **Async-Ready**: FastAPI has first-class async/await support. This future-proofs us for the AI triage and webhook integrations where I/O-bound concurrency will matter.
3. **Flexibility**: SQLAlchemy 2.0 gives us full control over the data layer, and the migration strategy (Alembic) is database-agnostic. Switching from SQLite to PostgreSQL later is a connection-string change.
4. **Modern Python**: Pydantic v2 (used by FastAPI) offers significantly better performance and stricter type validation than Django's form/serializer system.
5. **Lightweight**: A FastAPI project can remain a simple Python package. Django's app-based structure would introduce boilerplate we don't need for the current scope.

Django would make sense if we needed an immediate admin UI or a monolithic full-stack web app. Since the front-end is deferred and we are building API-first, FastAPI is the pragmatic choice.

---

## 2. High-Level Architecture

The system follows a classic layered architecture to keep concerns separated and testing straightforward.

```
┌─────────────────────────────────────────────┐
│              Consumer Layer                  │
│  (Future: Web UI, CLI, Email Workers)        │
└────────────────────┬────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────┐
│              API Layer                       │
│  FastAPI Routers                             │
│  - Input Validation (Pydantic)               │
│  - Dependency Injection                      │
│  - Exception Handling                        │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│            Service Layer                     │
│  - Business Logic                            │
│  - State Machine Enforcement                 │
│  - Audit Log Generation                      │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│           Repository Layer                   │
│  - SQLAlchemy Queries & Transactions         │
│  - Model-to-Domain Mapping                   │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│             Data Layer                       │
│   SQLite (MVP)  ←→  PostgreSQL (Future)    │
│   Alembic Migrations                         │
└─────────────────────────────────────────────┘
```

**Design Principles:**
- **Dependency Rule**: Each layer depends only on the layer directly below it.
- **Interface Segregation**: The repository layer is abstracted so the service layer doesn't know if it's talking to SQLite or PostgreSQL.
- **Immutability**: Audit logs are append-only. No updates, no deletes.

---

## 3. Project Directory Structure

```
superticket-project/
│
├── superticket/
│   ├── __init__.py
│   ├── main.py              # FastAPI application factory & lifespan events
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic-settings based configuration management
│   │   ├── exceptions.py    # Custom domain exceptions
│   │   └── dependencies.py  # FastAPI dependency injection setup
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── auth.py        # User registration, login, and profile endpoints
│   │       └── tickets.py     # Ticket CRUD & state transition endpoints
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── ticket.py          # Pydantic request & response DTOs
│   │   └── user.py            # Pydantic user schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py            # Password hashing, JWT management, user CRUD
│   │   ├── ticket.py          # Ticket business logic & state machine
│   │   └── audit.py           # Audit log recording service
│   ├── repository/
│   │   ├── __init__.py
│   │   └── ticket.py          # SQLAlchemy data access for tickets
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py           # TicketState and UserRole enums
│   │   ├── ticket.py          # SQLAlchemy ORM tables
│   │   └── user.py            # SQLAlchemy user model
│   └── db/
│       ├── __init__.py
│       ├── engine.py        # SQLAlchemy engine & session factory
│       └── base.py          # DeclarativeBase & connection helpers
│
├── alembic/                 # Database migration scripts
│   ├── versions/
│   └── env.py
│
├── tests/                   # Test suite (deferred pending test runner selection)
│   └── ...
│
├── .env.example             # Example environment variables
├── pyproject.toml           # Project metadata & dependencies
├── README.md                # Human-facing project overview
├── SPECS.md                 # Original system specification
└── DESIGN.md                # This file
```

---

## 4. Database Strategy

### Technology Stack
- **ORM**: SQLAlchemy 2.0 (declarative mapping, type hints)
- **Migrations**: Alembic (version-controlled schema evolution)
- **Initial DB**: SQLite (file-based, zero-config)
- **Future DB**: PostgreSQL (via `psycopg3`)

### Flexibility for PostgreSQL Migration
The engine factory in `superticket/db/engine.py` will read the connection string from a `DATABASE_URL` environment variable. Moving from SQLite to PostgreSQL requires only:
1. Swapping `sqlite3` for `psycopg` in dependencies.
2. Updating the `.env` file with a PostgreSQL connection string.
3. Running `alembic upgrade head`.

### Core Entities (MVP)

**`Ticket` Model:**
| Column        | Type     | Constraints              |
|---------------|----------|--------------------------|
| id            | String   | Primary Key (e.g., INC-2024-001) |
| requester_id  | String   | Not Null                 |
| category      | String   | Not Null                 |
| sub_category  | String   | Not Null                 |
| item          | String   | Not Null                 |
| urgency       | Enum     | LOW, MEDIUM, HIGH        |
| impact        | Enum     | INDIVIDUAL, DEPT, ORG    |
| priority      | Enum     | Computed: Urgency x Impact |
| state         | Enum     | NEW, TRIAGE, ASSIGNED, IN_PROGRESS, PENDING_VENDOR, RESOLVED, CLOSED |
| created_at    | DateTime | Default: now()           |
| updated_at    | DateTime | On Update: now()         |

**`AuditLog` Model:**
| Column        | Type     | Constraints              |
|---------------|----------|--------------------------|
| id            | UUID     | Primary Key              |
| ticket_id     | String   | Foreign Key → Ticket.id  |
| action        | String   | Not Null                 |
| old_value     | JSON     | Nullable                 |
| new_value     | JSON     | Not Null                 |
| performed_by  | String   | Nullable                 |
| timestamp     | DateTime | Default: now()           |

**`User` Model:**
| Column         | Type     | Constraints              |
|----------------|----------|--------------------------|
| id             | UUID     | Primary Key              |
| email          | String   | Unique, Indexed, Not Null|
| hashed_password| String   | Not Null                 |
| full_name      | String   | Not Null                 |
| role           | String   | Not Null, Default: "user"|
| is_active      | Boolean  | Not Null, Default: True  |
| created_at     | DateTime | Default: now()           |
| updated_at     | DateTime | On Update: now()         |

---

## 5. State Machine Design

The ticket lifecycle is strictly enforced by the `TicketService` layer.

### States
1. `NEW` — Initial state upon creation.
2. `TRIAGE` — Undergoing initial classification.
3. `ASSIGNED` — Allocated to an agent.
4. `IN_PROGRESS` — Agent is actively working.
5. `PENDING_VENDOR` — Waiting for external resolution.
6. `RESOLVED` — Solution provided, awaiting closure.
7. `CLOSED` — Final state.

### Transition Rules
- **Linear Progression**: A ticket **cannot** move to `CLOSED` without first passing through `RESOLVED`.
- **Re-opening (Deferred)**: Replying to a `RESOLVED` ticket within 48h moves it to `IN_PROGRESS`. After 48h, a new linked ticket is created.
- **Pending Timers (Deferred)**: Moving to `PENDING_VENDOR` pauses the SLA clock.
- **No Backward Jumps**: Moving from `ASSIGNED` back to `NEW` is invalid.

### Implementation
- A dictionary mapping states to valid next states will live in `services/ticket.py`.
- The service layer throws a custom `InvalidStateTransition` exception if rules are violated.
- Every successful transition triggers an `AuditLog` entry.

---

## 6. API Design (MVP)

Base path: `/api/v1`

### Endpoints

**Ticket Endpoints:**

| Method | Path                  | Description                     | Auth |
|--------|-----------------------|---------------------------------|------|
| POST   | `/tickets`            | Create a new ticket             | Yes  |
| GET    | `/tickets`            | List tickets (paginated)        | Yes  |
| GET    | `/tickets/{id}`       | Get a specific ticket           | Yes  |
| PATCH  | `/tickets/{id}`       | Update ticket fields            | Yes  |
| POST   | `/tickets/{id}/transition` | Trigger a state change      | Yes  |
| GET    | `/tickets/{id}/audit` | Get the immutable audit log     | Yes  |

**Auth Endpoints:**

| Method | Path                  | Description                     | Auth |
|--------|-----------------------|---------------------------------|------|
| POST   | `/auth/register`      | Register a new user             | No   |
| POST   | `/auth/token`         | Login, return JWT access token  | No   |
| GET    | `/auth/me`            | Get current user profile        | Yes  |

All ticket endpoints require a valid JWT in the `Authorization: Bearer <token>` header. The `performed_by` field on audit logs is auto-populated from the authenticated user's email.

### Error Handling
- `400 Bad Request`: Invalid state transition, Pydantic validation error.
- `404 Not Found`: Ticket ID does not exist.
- `401 Unauthorized`: Missing or invalid JWT token.

All errors follow a standard JSON structure:
```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE_FOR_CLIENTS"
}
```

---

## 7. Versioning Strategy

We use semantic versioning with explicit stage suffixes:

- **Alpha**: `x.x.x-alpha.x` — Active development, API may change.
- **Beta**: `x.x.x-beta.x` — Feature-complete, testing & bug-fixing.
- **Release**: `x.x.x` — Stable, production-ready.

**Current Version**: `0.1.0-alpha.1` (MVP Development)

---

## 8. Future Milestones (Deferred)

These features are intentionally out of scope for the current MVP to keep complexity low.

| Milestone | Version       | Feature                                      |
|-----------|---------------|----------------------------------------------|
| 2         | alpha.2       | Local DB user authentication                  |
| 3         | alpha.3       | Web UI (Self-Service Portal, Agent Workspace)|
| 4         | alpha.4       | LLM Triage Integration (OpenAI-compatible)   |
| 5         | beta.1        | Email-to-Ticket Processing                   |
| 6         | beta.2        | Webhook Subscriptions (Slack, Teams, Jira)   |
| 7         | beta.3        | SLA Management Engine & Breach Alerts        |
| 8         | 0.1.0-rc1     | Containerization (Docker)                    |
| 9         | 0.1.0-rc2     | Enterprise SSO authentication (OAuth2 / SAML)|

---

## 9. Configuration & Environment

Environment variables will be loaded via `pydantic-settings` from a `.env` file:

```env
DATABASE_URL=sqlite:///./superticket.db
DEBUG=True
APP_VERSION=0.1.0-alpha.1
SECRET_KEY=your-secret-key-here
```

This keeps secrets out of the codebase and makes the application 12-factor compliant.

---

## 10. Testing Strategy

**Current State**: Test infrastructure is fully configured and operational.

**Active Stack**:
- **Runner**: `pytest`
- **Coverage**: `pytest-cov`
- **HTTP Client**: `httpx` (via FastAPI `TestClient`)
- **Fixtures**: `pytest-asyncio` for async service tests
- **DB**: Session-scoped SQLite in-memory engine with function-scoped transaction rollback fixtures (`tests/conftest.py`)

**Test Suite**: 69 tests covering the state machine, service layer, API endpoints, and ORM models.

---

## 11. Decisions Log

| Date       | Decision                              | Rationale                                      |
|------------|---------------------------------------|------------------------------------------------|
| 2026-05-10 | FastAPI over Django                   | API-first goal, async support, modern Python   |
| 2026-05-10 | SQLite → PostgreSQL (Future)          | Zero-config MVP, flexibility via SQLAlchemy    |
| 2026-05-10 | Custom State Machine in Service Layer | Business logic must be separated from DB layer |
| 2026-05-10 | Pydantic v2                           | Performance, strict typing, FastAPI native     |
| 2026-05-15 | Local DB auth (bcrypt + JWT)          | Simple, no external IdP dependency for MVP     |
| 2026-05-15 | OAuth2/SAML deferred to rc2           | Enterprise SSO is a deployment concern, not core logic |
