"""LLM-based triage service for automatic ticket classification."""

import json
import logging

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from superticket.core.config import settings
from superticket.data.mock_kb import search_kb
from superticket.models.enums import TicketState
from superticket.services.ticket import TicketService

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are an IT service desk triage assistant. Analyze the ticket description and return a JSON object with the following structure:

{
  "category": "<one of: Access, Network, Hardware, Software>",
  "sub_category": "<relevant sub-category based on category>",
  "item": "<specific item within sub-category>",
  "sentiment_score": <float between -1.0 (very frustrated) and 1.0 (positive)>,
  "pii_detected": <boolean: true if the description contains passwords, credit card numbers, or other sensitive data>,
  "suggested_resolution": "<brief suggested solution referencing a KB article if applicable, or empty string>",
  "confidence_score": <float between 0.0 and 1.0 indicating your confidence in classification>
}

Available categories and sub-categories:
- Access > Account (tags: password, login, account, lock, security)
- Network > VPN (tags: vpn, network, remote), Wi-Fi (tags: wifi, connectivity), File Sharing (tags: drive, share, files)
- Hardware > Laptop (tags: screen, display, flicker, keyboard, keys), Printer (tags: printer, setup)
- Software > Bug (tags: crash, app, software), Email (tags: email, sync, outlook)

Rules:
1. Return ONLY the JSON object, no other text or formatting.
2. If PII is detected, set pii_detected to true but do NOT include any sensitive data in your response.
3. sentiment_score should reflect the user's tone: frustrated/urgent = negative, calm/neutral = 0, positive = high.
4. For suggested_resolution, reference the KB article content if one matches the issue. If no match, leave empty string.
5. confidence_score should be low (<0.5) if you are uncertain about classification.\
"""


async def triage_ticket(
    ticket_id: str,
    session_factory,
) -> None:
    """Run LLM triage on a newly created ticket and transition to TRIAGE state.

    This is designed as a fire-and-forget async task. It opens its own DB session.
    """
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping triage for ticket %s", ticket_id)
        return

    db: Session = session_factory()
    try:
        ticket = TicketService.get(db, ticket_id)
    except Exception as e:
        logger.error("Failed to fetch ticket %s for triage: %s", ticket_id, e)
        db.close()
        return

    if ticket.state != TicketState.NEW.value or not ticket.description:
        db.close()
        return

    description = ticket.description.strip()
    if not description:
        db.close()
        return

    # Search KB for context
    kb_context = _build_kb_context(description)

    try:
        result = await _call_llm(ticket_id, description, kb_context)
    except Exception as e:
        logger.error("LLM triage failed for ticket %s: %s", ticket_id, e)
        db.close()
        return

    if result is None:
        logger.warning("LLM returned no result for ticket %s", ticket_id)
        db.close()
        return

    # Update ticket with AI results
    ticket.ai_category = result.get("category")
    ticket.ai_sub_category = result.get("sub_category")
    ticket.ai_item = result.get("item")
    sentiment = result.get("sentiment_score")
    if isinstance(sentiment, (int, float)):
        ticket.sentiment_score = max(-1.0, min(1.0, float(sentiment)))
    pii_raw = result.get("pii_detected", False)
    ticket.pii_detected = bool(pii_raw)
    ticket.suggested_resolution = result.get("suggested_resolution")
    confidence = result.get("confidence_score")
    if isinstance(confidence, (int, float)):
        ticket.confidence_score = max(0.0, min(1.0, float(confidence)))

    # Transition to TRIAGE state
    try:
        TicketService.transition_state(
            db,
            ticket_id,
            TicketState.TRIAGE,
            performed_by="system",
        )
    except Exception as e:
        logger.error("Failed to transition ticket %s to TRIAGE after triage: %s", ticket_id, e)

    db.close()
    logger.info(
        "Triage completed for ticket %s: category=%s confidence=%.2f",
        ticket_id,
        result.get("category"),
        result.get("confidence_score", 0),
    )


def _build_kb_context(description: str) -> str:
    """Search KB and return context string for the LLM prompt."""
    results = search_kb(query=description[:100])
    if not results:
        return ""

    parts = []
    for article in results[:3]:
        parts.append(
            f"KB [{article.category}/{article.sub_category}] "
            f"{article.title}: {article.content}"
        )
    return "\n\nRelevant KB articles:\n" + "\n".join(parts)


async def _call_llm(ticket_id: str, description: str, kb_context: str) -> dict | None:
    """Call the OpenAI-compatible LLM and parse the JSON response."""
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    user_message = (
        f"Ticket ID: {ticket_id}\n\nDescription:\n{description}"
        + kb_context
    )

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
    )

    content = response.choices[0].message.content.strip()
    if not content:
        return None

    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        logger.warning("LLM returned non-JSON for ticket %s. Raw response (first 200 chars): %s", ticket_id, content[:200])

    # Try to extract JSON from markdown code block
    stripped = content.strip()
    if stripped.startswith("```"):
        inner = stripped.split("\n", 1)[-1]
        if inner.endswith("```"):
            inner = inner[:-3].strip()
        try:
            result = json.loads(inner)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    logger.warning("Failed to parse LLM response as JSON for ticket %s", ticket_id)
    return None


def confirm_triage(
    session: Session,
    ticket_id: str,
    *,
    category: str | None = None,
    sub_category: str | None = None,
    item: str | None = None,
    urgency: str | None = None,
    impact: str | None = None,
    override_reason: str | None = None,
    performed_by: str | None = None,
) -> None:
    """Confirm or override AI triage results and log the ground truth.

    If human values differ from AI suggestions, records a TriageOverrideLog entry.
    Then applies the final classification to the ticket and transitions to ASSIGNED.
    """
    from superticket.models.triage_log import TriageOverrideLog
    from superticket.services.ticket import _compute_priority

    ticket = TicketService.get(session, ticket_id)

    human_category = category or ticket.category
    human_sub_category = sub_category or ticket.sub_category
    human_item = item or ticket.item
    human_urgency = urgency or ticket.urgency
    human_impact = impact or ticket.impact

    ai_cat = ticket.ai_category
    ai_sub = ticket.ai_sub_category
    ai_item_val = ticket.ai_item

    # Check if any override occurred
    has_override = (
        (ai_cat is not None and ai_cat.lower() != human_category.lower())
        or (ai_sub is not None and ai_sub.lower() != human_sub_category.lower())
        or (ai_item_val is not None and ai_item_val.lower() != human_item.lower())
    )

    if has_override:
        log = TriageOverrideLog(
            ticket_id=ticket_id,
            ai_category=ai_cat,
            human_category=human_category,
            ai_sub_category=ai_sub,
            human_sub_category=human_sub_category,
            ai_item=ai_item_val,
            human_item=human_item,
            override_reason=override_reason,
            performed_by=performed_by,
        )
        session.add(log)

    priority = _compute_priority(human_urgency, human_impact)
    TicketService.update(
        session,
        ticket_id,
        category=human_category,
        sub_category=human_sub_category,
        item=human_item,
        urgency=human_urgency,
        impact=human_impact,
        priority=priority,
        performed_by=performed_by,
    )

    TicketService.transition_state(
        session,
        ticket_id,
        TicketState.ASSIGNED,
        performed_by=performed_by,
    )
