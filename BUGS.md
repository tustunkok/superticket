# Known Bugs

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

## Bug 9: Password minimum length mismatch between API and web form (LOW)

**Affected files:**
- `schemas/user.py:15` — `password: str = Field(min_length=8)`
- `views/auth.py:73` — `password: str = Form(min_length=6)`
- `templates/register.html:63` — `minlength="6"` and "At least 6 characters"

**Current behavior:** The API schema requires minimum 8 characters. The web form uses `minlength="6"` and says "At least 6 characters". A password of 7 characters would pass the web form validation but fail the API endpoint.

**Expected behavior:** Consistent minimum length across all paths (recommend 8).
