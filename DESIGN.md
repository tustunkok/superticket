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

Django would make sense if we needed an immediate admin UI or a monolithic full-stack web app. The project started as API-first but evolved to include a Jinja2-rendered web UI for the self-service portal, agent workspace, and admin interface. FastAPI remains the pragmatic choice because it supports both REST APIs and server-side HTML rendering without friction.

---

## 2. High-Level Architecture

The system follows a classic layered architecture to keep concerns separated and testing straightforward.

```
┌─────────────────────────────────────────────┐
│              Consumer Layer                  │
│  (Web UI: Jinja2 + Starlette static files)   │
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
│  - Direct SQLAlchemy ORM queries             │
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
- **No Repository Layer**: The originally-planned repository abstraction was not implemented; the service layer queries SQLAlchemy ORM directly. This simplifies the architecture and reduces indirection. The database is still swapable via `DATABASE_URL`.
- **Immutability**: Audit logs are append-only. No updates, no deletes.

---

## 3. Project Directory Structure

```
superticket-project/
│
├── superticket/
│   ├── __init__.py
│   ├── main.py              # FastAPI application factory & lifespan events
│   ├── template_engine.py   # Jinja2 template engine setup
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic-settings based configuration management
│   │   ├── exceptions.py    # Custom domain exceptions
│   │   ├── dependencies.py  # FastAPI dependency injection setup
│   │   └── flash.py         # Flash message utility (Starlette session cookies)
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py        # User registration, login, and profile endpoints
│   │       ├── tickets.py     # Ticket CRUD & state transition endpoints
│   │       └── comments.py    # Comment create/list endpoints for tickets
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── ticket.py          # Pydantic request & response DTOs
│   │   ├── user.py            # Pydantic user schemas
│   │   ├── comment.py         # Pydantic comment DTOs
│   │   └── kb.py              # Pydantic knowledge base article schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py            # Password hashing, JWT management, user CRUD
│   │   ├── ticket.py          # Ticket business logic & transitions
│   │   ├── state_machine.py   # State machine transition rules (VALID_TRANSITIONS dict)
│   │   └── comment.py         # Comment creation and retrieval logic
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py           # TicketState, UrgencyLevel, ImpactScope, PriorityLevel enums
│   │   ├── ticket.py          # SQLAlchemy ORM: Ticket + AuditLog tables
│   │   ├── user.py            # SQLAlchemy user model
│   │   └── comment.py         # SQLAlchemy comment model (public/internal)
│   ├── views/                 # Web UI route handlers (Jinja2 rendered)
│   │   ├── __init__.py
│   │   ├── auth.py            # Login, register, logout HTML routes
│   │   ├── portal.py          # Self-service user ticket submission & viewing
│   │   ├── agent.py           # Agent workspace: ticket assignment & management
│   │   ├── admin.py           # Admin user management interface
│   │   └── kb.py              # Knowledge base browsing routes
│   ├── templates/             # Jinja2 HTML templates for web UI
│   ├── static/                # Static files (CSS, JS) — currently empty
│   ├── data/                  # Data fixtures and mock data
│   │   └── mock_kb.py         # Mock knowledge base articles for development
│   └── db/
│       ├── __init__.py
│       ├── engine.py        # SQLAlchemy engine & session factory
│       └── base.py          # DeclarativeBase & connection helpers
│
├── alembic/                 # Database migration scripts
│   ├── versions/
│   │   ├── 192fe95e38b2_create_tickets_and_audit_logs_tables.py
│   │   ├── 0de2fd07dea8_add_users_table.py
│   │   ├── c9142fe9cb10_add_description_to_tickets.py
│   │   ├── 32b9f4aa9e49_add_assigned_to_to_tickets.py
│   │   ├── 51adc2175062_add_comments_table.py
│   │   └── 5d1a79e9b4dc_add_ticket_indexes.py
│   └── env.py
│
├── tests/                   # Test suite (pytest + pytest-asyncio)
│   ├── conftest.py          # Fixtures: DB sessions, test clients, factory helpers
│   ├── test_api.py          # REST API endpoint tests
│   ├── test_auth_api.py     # Auth API endpoint tests
│   ├── test_auth_service.py # Auth service logic tests
│   ├── test_comment_api.py  # Comment API endpoint tests
│   ├── test_comment_service.py # Comment service logic tests
│   ├── test_flash.py        # Flash message utility tests
│   ├── test_models.py       # ORM model tests
│   ├── test_service.py      # Ticket service layer tests
│   ├── test_state_machine.py# State machine transition tests
│   ├── test_web_ui.py       # Web UI route and template rendering tests
│   └── test_admin.py        # Admin user management tests
│
├── main.py                  # Entry-point scaffold (prints greeting)
├── pyproject.toml           # Project metadata & dependencies (PEP 621, uv)
├── README.md                # Human-facing project overview
├── SPECS.md                 # Original system specification
└── DESIGN.md                # This file
```

> **Note**: The originally-planned `repository/` layer and `services/audit.py` were not implemented. Audit logging is handled inline within the ticket service, and queries go directly through SQLAlchemy ORM relationships (e.g., `ticket.audit_logs`, `ticket.comments`).

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
| description   | Text     | Nullable                 |
| requester_id  | String   | Not Null                 |
| assigned_to   | String   | Nullable (FK → User.email)|
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

**`Comment` Model:**
| Column        | Type     | Constraints              |
|---------------|----------|--------------------------|
| id            | UUID     | Primary Key              |
| ticket_id     | String   | Foreign Key → Ticket.id  |
| author_email  | String   | Not Null                 |
| body          | Text     | Not Null                 |
| is_internal   | Boolean  | Default: False           |
| created_at    | DateTime | Default: now()           |

**`User` Model:**

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

- **Linear Progression**: A ticket cannot move to `CLOSED` without first passing through `RESOLVED`. From `NEW`, one-step-forward skips are allowed (e.g., NEW → ASSIGNED, bypassing TRIAGE).
- **Re-opening (Partial)**: A `RESOLVED` ticket can transition back to `IN_PROGRESS` in the state machine. The 48-hour window logic is deferred; any re-open moves to `IN_PROGRESS`.
- **Pending Timers (Deferred)**: Moving to `PENDING_VENDOR` pauses the SLA clock.
- **No Backward Jumps**: Moving from `ASSIGNED` back to `NEW` or `TRIAGE` is invalid.

### Valid Transitions (as implemented)

| From        | To                              |
|-------------|----------------------------------|
| NEW         | TRIAGE, ASSIGNED                 |
| TRIAGE      | ASSIGNED                         |
| ASSIGNED    | IN_PROGRESS, PENDING_VENDOR      |
| IN_PROGRESS | PENDING_VENDOR, RESOLVED         |
| PENDING_VENDOR | IN_PROGRESS, RESOLVED         |
| RESOLVED    | CLOSED, IN_PROGRESS              |
| CLOSED      | *(terminal — no transitions)*   |

### Implementation

- A dictionary mapping states to valid next states lives in `services/state_machine.py` (`VALID_TRANSITIONS`).
- The service layer throws a custom `InvalidStateTransition` exception if rules are violated.
- Every successful transition triggers an `AuditLog` entry (handled inline in the ticket service).

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

**Comment Endpoints:**

| Method | Path                              | Description                             | Auth |
|--------|-----------------------------------|-----------------------------------------|------|
| POST   | `/tickets/{ticket_id}/comments`   | Create a comment on a ticket            | Yes  |
| GET    | `/tickets/{ticket_id}/comments`   | List comments (paginated, filterable by internal/public) | Yes |

**Auth Endpoints:**

| Method | Path                  | Description                     | Auth |
|--------|-----------------------|---------------------------------|------|
| POST   | `/auth/register`      | Register a new user             | No   |
| POST   | `/auth/token`         | Login, return JWT access token  | No   |
| GET    | `/auth/me`            | Get current user profile        | Yes  |

**Web UI Routes (Jinja2-rendered HTML):**

| Path              | Description                                   | Auth |
|-------------------|-----------------------------------------------|------|
| `/login`          | Login page                                    | No   |
| `/register`       | User registration page                        | No   |
| `/logout`         | Log out and redirect to login                 | Yes  |
| `/portal/`        | Self-service ticket listing                   | Yes  |
| `/portal/tickets/{id}` | View a single ticket as requester       | Yes  |
| `/portal/new`     | Create a new ticket form                      | Yes  |
| `/agent/tickets`  | Agent workspace — list and manage tickets     | Yes (agent/admin) |
| `/agent/tickets/{id}` | Agent view of a single ticket           | Yes (agent/admin) |
| `/admin/users`    | Admin user management — list, role/active toggle, delete | Yes (admin) |
| `/kb/`            | Browse knowledge base articles                | No   |

**Knowledge Base Endpoint:**

| Method | Path                  | Description                     | Auth |
|--------|-----------------------|---------------------------------|------|
| GET    | `/articles`           | List KB articles with search    | No   |

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

**Current Version**: `0.1.0-beta.1` (MVP Development)

---

## 8. Milestones

### Implemented

| Milestone | Version       | Feature                                      | Completion |
|-----------|---------------|----------------------------------------------|------------|
| 1         | alpha.1       | Ticket CRUD, State Machine, REST API Layer   | 2026-05-15 |
| 2         | alpha.2       | Local DB user authentication (bcrypt + JWT)  | 2026-05-15 |
| 2.5       | alpha.2.x     | Ticket `description` field + Comment model   | 2026-05-15 |
| 3         | beta.1        | Web UI (Self-Service Portal, Agent Workspace) | 2026-05-16 |
| 3.5       | beta.1.x     | Prevent comments on CLOSED tickets        | 2026-05-16 |
| 3.6       | beta.1.x     | Admin user management interface         | 2026-05-16 |

> **⚠ Known Issue**: Alembic migration `51adc2175062_add_comments_table.py` has empty `upgrade()`/`downgrade()` functions and performs no DDL. The comments table was likely created by SQLAlchemy's declarative mapping rather than through Alembic. This should be fixed before running migrations on a fresh database.

### Future Milestones (Deferred)

These features are intentionally out of scope for the current MVP to keep complexity low.

| Milestone | Version       | Feature                                      |
|-----------|---------------|----------------------------------------------|
| 4         | alpha.4       | LLM Triage Integration (OpenAI-compatible)   |
| 5         | beta.1        | Email-to-Ticket Processing                   |
| 6         | beta.2        | Webhook Subscriptions (Slack, Teams, Jira)   |
| 7         | beta.3        | SLA Management Engine & Breach Alerts        |
| 8         | 0.1.0-rc1     | Containerization (Docker)                    |
| 9         | 0.1.0-rc2     | Enterprise SSO authentication (OAuth2 / SAML)|

---

## 9. Configuration & Environment

Environment variables are loaded via `pydantic-settings` from a `.env` file (see `core/config.py`). The current settings class defines:

| Setting | Env Var | Default Value | Description |
|---------|---------|---------------|-------------|
| database_url | DATABASE_URL | `sqlite:///./superticket.db` | SQLAlchemy connection string |
| debug | DEBUG | `False` | Debug mode for development |
| app_version | APP_VERSION | *(see config.py)* | Application version displayed in API docs |
| secret_key | SECRET_KEY | *insecure dev default* | Signing key for JWT + session cookies — **must change in production** |
| algorithm | ALGORITHM | `HS256` | JWT signing algorithm |
| access_token_expire_minutes | ACCESS_TOKEN_EXPIRE_MINUTES | `30` | JWT token expiration window |

> **Note**: The default `app_version` in `core/config.py` may lag behind the version in `pyproject.toml`. When releasing a new version, update both locations. No `.env.example` file exists yet; create one from the table above for onboarding.

---

## 10. Testing Strategy

**Current State**: Test infrastructure is fully configured and operational.

**Active Stack**:
- **Runner**: `pytest`
- **Coverage**: `pytest-cov`
- **HTTP Client**: `httpx` (via FastAPI `TestClient`)
- **Fixtures**: `pytest-asyncio` for async service tests
- **DB**: Session-scoped SQLite in-memory engine with function-scoped transaction rollback fixtures (`tests/conftest.py`)

**Test Suite**: 201 tests covering the state machine, service layer, API endpoints, web UI routes, ORM models, authentication, and admin user management.

---

## 11. Decisions Log

| Date       | Decision                              | Rationale                                      |
|------------|---------------------------------------|------------------------------------------------|
| 2026-05-10 | FastAPI over Django                   | API-first goal, async support, modern Python   |
| 2026-05-10 | SQLite → PostgreSQL (Future)          | Zero-config MVP, flexibility via SQLAlchemy    |
| 2026-05-10 | Custom State Machine in Service Layer | Business logic must be separated from DB layer; transition rules live in `services/state_machine.py` |
| 2026-05-10 | Pydantic v2                           | Performance, strict typing, FastAPI native     |
| 2026-05-15 | Local DB auth (bcrypt + JWT)          | Simple, no external IdP dependency for MVP     |
| 2026-05-15 | OAuth2/SAML deferred to rc2           | Enterprise SSO is a deployment concern, not core logic |
| 2026-05-15 | Jinja2 web UI over SPA                | Server-side rendering avoids build toolchain complexity for MVP; easier to prototype portal/agent/admin views quickly |
| 2026-05-15 | No Repository Layer                    | Original design called for a repository abstraction between services and SQLAlchemy. It was deemed unnecessary indirection — the service layer queries ORM relationships directly, keeping code simple and testable |
