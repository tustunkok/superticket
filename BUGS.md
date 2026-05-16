# Known Bugs

## Bug 1: No admin user management interface (HIGH)

**Affected area:** Admin role, user management

**Current behavior:** The `admin` role is defined in `models/enums.py:18-23` and an admin user is seeded at startup, but no admin-only routes or UI exists for listing, editing, or deactivating users. Additionally, the unauthenticated `POST /api/v1/auth/register` endpoint accepts a `role` field from the request body (`schemas/user.py:17`), allowing anyone to register as `admin` by sending `"role": "admin"` in the JSON body. The test at `tests/test_auth_api.py:94-105` explicitly validates this and expects `201`.

**Expected behavior:**
- An admin-only page (e.g., `/admin/users`) to list all registered users with options to change roles, activate/deactivate accounts, and delete users.
- The `UserCreate` schema should either remove the `role` field entirely (always defaulting to `"user"`) or the admin user management API should be the only path to set non-user roles.

---

## Bug 2: Comments can be added to CLOSED tickets (HIGH)

**Affected routes:**
- `POST /portal/tickets/{ticket_id}/comments` (`views/portal.py:127-144`)
- `POST /agent/tickets/{ticket_id}/comments` (`views/agent.py:111-132`)
- `POST /api/v1/tickets/{ticket_id}/comments` (`api/v1/comments.py:15-33`)

**Current behavior:** `CommentService.create` (`services/comment.py:15-37`) only checks that the ticket exists (line 24-26), not its state. The state machine (`services/state_machine.py:31`) defines `CLOSED` as a terminal state with no valid transitions, but this is not enforced for comment creation. Users and agents can continue adding comments indefinitely on closed tickets.

**Expected behavior:** `CommentService.create` (or each route) should check `ticket.state == TicketState.CLOSED.value` and reject the comment with an appropriate error. On the web side, the comment form in `portal/ticket_detail.html:24-28` should be conditionally hidden when the ticket is CLOSED.

**Related:** Web comment routes don't catch domain exceptions (`TicketNotFound`, etc.) — a browser user would see raw JSON instead of an error page.

---

## Bug 3: Navbar logo redirects to /login for authenticated users (MEDIUM)

**Affected files:**
- `templates/base.html:64` — `<a class="navbar-brand" href="/">...SuperTicket</a>`
- `main.py:109-112` — `@app.get("/")` unconditionally returns `RedirectResponse(url="/login")`

**Current behavior:** The "SuperTicket" brand link always navigates to `/`. The root route `/` unconditionally redirects to `/login`, even when the user is already authenticated. A logged-in user clicking the logo gets kicked to the login page.

**Expected behavior:** The root route should check authentication and redirect authenticated users to their appropriate dashboard (`/portal/` for users, `/agent/tickets` for agents/admins), only redirecting unauthenticated users to `/login`. Alternatively, the navbar link could point to a context-appropriate URL based on the user's role.

---

## Bug 4: Agent role guard is a no-op and never called (MEDIUM)

**Affected file:** `views/agent.py:18-20`

**Current behavior:** The `_require_agent` function checks `if current_user.role not in ("agent", "admin"): pass` — the entire body is `pass`, so it does nothing. Additionally, this function is never called by any route. All agent routes use `get_current_active_user_from_cookie` as their dependency, which only verifies authentication and active status, not role.

**Expected behavior:** Agent routes should enforce that the user has the `agent` or `admin` role. Either call `_require_agent` in each agent view function (and raise `HTTPException(403)` instead of `pass`), or create a proper FastAPI dependency like `require_agent_role`.

---

## Bug 5: Flash messages are non-functional — toast system broken (MEDIUM)

**Affected files:**
- `template_engine.py:17` — `get_flashed_messages: lambda: []`
- `templates/base.html:90-96` — toast container

**Current behavior:** The Jinja2 global `get_flashed_messages` is hardcoded to return an empty list. The toast container in `base.html` iterates over `get_flashed_messages()`, which always yields nothing. No success, error, or info feedback is ever shown in the UI after form submissions or redirects.

**Expected behavior:** Flash messages should be wired to session state (e.g., via cookies or a middleware) so that messages set before a redirect are actually rendered as toasts on the destination page.

---

## Bug 6: Web views fetch all 1000 tickets and filter/paginate in-memory (MEDIUM)

**Affected files:**
- `views/portal.py:33-34` — portal dashboard
- `views/agent.py:46-59` — agent ticket queue

**Current behavior:** Both views call `TicketService.list_(db, skip=0, limit=1000)` and then filter by `requester_id` / `state` / `priority` / `assigned_to` in Python. Pagination (`skip`/`limit`) is applied to the in-memory list, not the database query. The DB query always fetches up to 1000 records regardless of what page is being viewed.

**Expected behavior:** Filtering and pagination should be pushed down to `TicketService.list_` (or new methods) with WHERE clauses and LIMIT/OFFSET on the SQL query.

---

## Bug 7: Exception handlers return JSON to browsers (MEDIUM)

**Affected files:** `main.py:88-101`, `views/portal.py:98`, `views/agent.py:91`

**Current behavior:** The global exception handlers for `TicketNotFound` and `InvalidStateTransition` always return `JSONResponse`. If a user browses to `/portal/tickets/INC-NONEXISTENT`, they see raw JSON (`{"detail": "...", "code": "TICKET_NOT_FOUND"}`) instead of an HTML error page.

**Expected behavior:** Exception handlers should check the request's `Accept` header. For `text/html` requests, render an error template; for API requests (JSON), continue returning JSON.

---

## Bug 8: Portal ticket filtering matches both UUID and email for requester_id (LOW)

**Affected file:** `views/portal.py:34`

**Current behavior:** `user_tickets = [t for t in all_tickets if t.requester_id == str(current_user.id) or t.requester_id == current_user.email]`. This dual match suggests `requester_id` may be stored differently depending on the creation path (UUID from web creation at line 78, or whatever value is sent via the API). This is fragile and could cause bugs.

**Expected behavior:** `requester_id` should be uniformly stored as one canonical identifier everywhere, and the filtering should use a single consistent comparison.

---

## Bug 9: Password minimum length mismatch between API and web form (LOW)

**Affected files:**
- `schemas/user.py:15` — `password: str = Field(min_length=8)`
- `views/auth.py:73` — `password: str = Form(min_length=6)`
- `templates/register.html:63` — `minlength="6"` and "At least 6 characters"

**Current behavior:** The API schema requires minimum 8 characters. The web form uses `minlength="6"` and says "At least 6 characters". A password of 7 characters would pass the web form validation but fail the API endpoint.

**Expected behavior:** Consistent minimum length across all paths (recommend 8).
