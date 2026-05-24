"""add_assigned_to_to_tickets

Revision ID: 32b9f4aa9e49
Revises: 51adc2175062
Create Date: 2026-05-24 10:49:25.785511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32b9f4aa9e49'
down_revision: Union[str, Sequence[str], None] = '51adc2175062'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tickets', sa.Column('assigned_to', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tickets', 'assigned_to')
