# Specification: Super Ticket Enterprise Ticketing System (to be v1.0)
## Project Focus: High-Velocity Ticketing & Hybrid AI Triage

### 1. Core Entity: The Ticket Anatomy
Each ticket must be a structured data object containing the following mandatory fields:

* **Identifier:** Unique Alphanumeric ID (e.g., INC-2024-001).
* **Requester Metadata:** User ID, Department, Location, Contact Method, VIP Status.
* **Classification:** 3-tier hierarchy (Category > Sub-category > Item).
* **Urgency:** User-defined impact level (Low, Medium, High).
* **Impact:** System/Agent-defined scope (Individual, Department, Organization).
* **Priority Matrix:** Calculated value based on `Urgency x Impact`.
* **State:** [New, Triage, Assigned, In Progress, Pending Vendor, Resolved, Closed].
* **Audit Log:** Immutable JSON array recording every change in state, ownership, or field value.

---

### 2. Hybrid Triage System Architecture
The system utilizes a two-gate process: an LLM "First Responder" and a Human "Dispatcher."

#### Phase A: LLM Analysis (Qwen 3.5 395B / Large Model)
Immediately upon intake, the LLM must perform:
* **Intent Extraction:** Map unstructured prose to the Service Catalog.
* **Sentiment Analysis:** Score -1.0 to 1.0; trigger alerts for highly frustrated users.
* **PII Scrubbing:** Detect and flag/mask passwords, credit card numbers, or sensitive IDs.
* **Suggested Resolution:** Match the ticket against the Knowledge Base and propose a "Likely Solution."
* **Confidence Score:** A percentage representing the AI's certainty in its classification.

#### Phase B: Human Triage Workspace (UI)
A dedicated "Command Center" view for Triage Officers:
* **Ghost-filling:** Show AI suggestions in the fields (italicized/greyed out) until confirmed by the human.
* **Hotkeys:** Support for rapid keyboard-only navigation (e.g., `Enter` to approve AI triage, `Shift+R` to re-categorize).
* **Batch Processing:** Ability to apply a single triage decision to multiple similar tickets identified by the AI.

---

### 3. Workflow & State Machine Logic
The platform must enforce strict transition rules to ensure data integrity:
* **Linear Progression:** A ticket cannot move to `Closed` without first passing through `Resolved`.
* **Re-opening Logic:** If a user replies to a `Resolved` ticket within 48 hours, move state to `In Progress`. If after 48 hours, create a new linked ticket.
* **Pending State Timers:** Moving to `Pending Vendor` must pause the SLA resolution clock.

---

### 4. Technical Requirements

#### SLA Management Engine
* **Definition:** Support multiple SLAs based on Priority (e.g., P1 = 15m Response, 2h Resolution).
* **Breach Alerts:** Webhook triggers to notify management 15 minutes before an SLA breach.

#### Communications Layer
* **Threaded Messaging:** Support for internal-only comments (Private) and user-facing replies (Public).
* **Email-to-Ticket:** Inbound mail processing that parses subject lines for Ticket IDs to prevent duplicates.

#### API & Integration
* **RESTful API:** Full CRUD operations for all entities.
* **Identity Provider:** OAuth2 / SAML integration for enterprise SSO.
* **Webhook Subscriptions:** For external integrations (Slack, Teams, Jira).

---

### 5. UI/UX Requirements

* **Self-Service Portal:** A simplified interface for non-technical users to submit requests and track status.
* **Agent Workspace:** Multi-tab interface allowing technicians to work on multiple tickets simultaneously without losing state.
* **Knowledge Base Integration:** A "side-car" UI component that automatically searches for help articles while an agent is typing a response.

---

### 6. AI Feedback Loop
* **Ground Truth Logging:** The system must record every instance where a human overrides an LLM suggestion.
* **Evaluation Dataset:** Exportable JSONL of human-corrected tickets to be used for future model fine-tuning or RAG (Retrieval-Augmented Generation) optimization.