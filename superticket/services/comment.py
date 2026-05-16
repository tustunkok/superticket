"""Comment business logic for SuperTicket."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from superticket.core.exceptions import TicketNotFound
from superticket.models.comment import Comment
from superticket.models.ticket import Ticket


class CommentService:
    """Encapsulates comment CRUD for tickets."""

    @staticmethod
    def create(
        session: Session,
        ticket_id: str,
        author_id,
        author_name: str,
        content: str,
        is_internal: bool = False,
    ) -> Comment:
        """Add a comment to a ticket."""
        ticket = session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar_one_or_none()
        if ticket is None:
            raise TicketNotFound(ticket_id)

        comment = Comment(
            ticket_id=ticket_id,
            author_id=author_id,
            author_name=author_name,
            content=content,
            is_internal=is_internal,
        )
        session.add(comment)
        session.commit()
        return comment

    @staticmethod
    def list_for_ticket(
        session: Session,
        ticket_id: str,
        *,
        include_internal: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Comment]:
        """List comments for a ticket, optionally excluding internal ones."""
        query = (
            select(Comment)
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if not include_internal:
            query = query.where(~Comment.is_internal)
        result = session.execute(query)
        return list(result.scalars().all())
