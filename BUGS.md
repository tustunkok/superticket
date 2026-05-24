# Known Bugs

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