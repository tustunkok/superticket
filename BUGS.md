# Known Bugs

## Bug 1: Dashboard templates do not extend base.html — unstyled UI

**Affected pages:** `/portal/`, `/portal/tickets/new`, `/agent/tickets`

**Cause:** The templates `portal/dashboard.html`, `portal/ticket_new.html`, and `agent/dashboard.html` are missing `{% extends "base.html" %}`. They render as raw HTML content blocks without the Bootstrap 5 CDN links, the navbar, or the footer. This makes the pages appear with broken/unstyled Bootstrap components (bare HTML with Bootstrap class names but no actual stylesheet loaded).

Pages that DO extend `base.html` (and render correctly):
- `portal/ticket_detail.html`
- `agent/ticket_workspace.html`
- `login.html` (standalone, includes its own Bootstrap CDN)

Pages that DO NOT extend `base.html` (broken):
- `portal/dashboard.html`
- `portal/ticket_new.html`
- `agent/dashboard.html`

**Fix:** Add `{% extends "base.html" %}` at the top of each affected template and wrap existing content in `{% block content %}...{% endblock %}`.

## Bug 2: Ticket ID link in agent queue points to a non-existent route → 404

**Affected page:** `/agent/tickets`

**Cause:** In `partials/ticket_list.html` line 16, the ticket ID link is:
```
<a href="{{ ticket_url_prefix }}/{{ ticket.id }}">
```
For the agent queue, `ticket_url_prefix` is set to `'/agent/tickets'`, producing links like `/agent/tickets/INC-XXXXX`. However, no `GET /agent/tickets/{ticket_id}` route exists — the workspace route is at `/agent/tickets/{ticket_id}/work`.

**Fix:** Either:
- Change `ticket_url_prefix` in `agent/dashboard.html` to `'/agent/tickets'` and add a `GET /agent/tickets/{ticket_id}` redirect route that forwards to `/agent/tickets/{ticket_id}/work`, OR
- Change the link pattern in the partial to use a separate URL pattern for agents (e.g., `{{ ticket_url_prefix }}/{{ ticket.id }}/work`), OR
- Replace `ticket_url_prefix` in `agent/dashboard.html` with `'/agent/tickets'` and update `ticket_list.html` to append `/work` when `ticket_url_prefix` contains `/agent`.
