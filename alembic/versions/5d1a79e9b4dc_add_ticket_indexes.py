"""add_ticket_indexes

Revision ID: 5d1a79e9b4dc
Revises: 32b9f4aa9e49
Create Date: 2026-05-24 10:50:06.168250

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5d1a79e9b4dc'
down_revision: Union[str, Sequence[str], None] = '32b9f4aa9e49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(op.f('ix_tickets_requester_id'), 'tickets', ['requester_id'])
    op.create_index(op.f('ix_tickets_state'), 'tickets', ['state'])
    op.create_index(op.f('ix_tickets_priority'), 'tickets', ['priority'])
    op.create_index(op.f('ix_tickets_assigned_to'), 'tickets', ['assigned_to'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tickets_assigned_to'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_priority'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_state'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_requester_id'), table_name='tickets')
