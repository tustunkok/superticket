"""add_ai_triage_columns

Revision ID: f74a884068b3
Revises: 5d1a79e9b4dc
Create Date: 2026-05-24 14:38:41.026605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f74a884068b3'
down_revision: Union[str, Sequence[str], None] = '5d1a79e9b4dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_not_exists(table, column):
    """Add a column to the table only if it doesn't already exist (idempotent)."""
    import sqlalchemy.exc as exc

    try:
        op.add_column(table, column)
    except exc.OperationalError as e:
        if "duplicate column name" in str(e):
            pass
        else:
            raise


def upgrade() -> None:
    """Add AI triage columns to tickets and create triage_override_logs table."""
    _add_column_if_not_exists("tickets", sa.Column("ai_category", sa.String(), nullable=True))
    _add_column_if_not_exists("tickets", sa.Column("ai_sub_category", sa.String(), nullable=True))
    _add_column_if_not_exists("tickets", sa.Column("ai_item", sa.String(), nullable=True))
    _add_column_if_not_exists("tickets", sa.Column("sentiment_score", sa.Float(), nullable=True))
    _add_column_if_not_exists("tickets", sa.Column("pii_detected", sa.Boolean(), server_default=sa.text('0'), nullable=False))
    _add_column_if_not_exists("tickets", sa.Column("suggested_resolution", sa.Text(), nullable=True))
    _add_column_if_not_exists("tickets", sa.Column("confidence_score", sa.Float(), nullable=True))

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "triage_override_logs" not in tables:
        op.create_table(
            "triage_override_logs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("ticket_id", sa.String(), sa.ForeignKey("tickets.id"), nullable=False),
            sa.Column("ai_category", sa.String(), nullable=True),
            sa.Column("human_category", sa.String(), nullable=True),
            sa.Column("ai_sub_category", sa.String(), nullable=True),
            sa.Column("human_sub_category", sa.String(), nullable=True),
            sa.Column("ai_item", sa.String(), nullable=True),
            sa.Column("human_item", sa.String(), nullable=True),
            sa.Column("override_reason", sa.Text(), nullable=True),
            sa.Column("performed_by", sa.String(), nullable=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        )


def _drop_column_if_exists(table, column):
    """Drop a column from the table only if it exists (idempotent)."""
    import sqlalchemy.exc as exc

    try:
        op.drop_column(table, column)
    except exc.OperationalError as e:
        if "no such column" in str(e):
            pass
        else:
            raise


def downgrade() -> None:
    """Remove AI triage columns and drop triage_override_logs table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "triage_override_logs" in tables:
        op.drop_table("triage_override_logs")

    _drop_column_if_exists("tickets", "confidence_score")
    _drop_column_if_exists("tickets", "suggested_resolution")
    _drop_column_if_exists("tickets", "pii_detected")
    _drop_column_if_exists("tickets", "sentiment_score")
    _drop_column_if_exists("tickets", "ai_item")
    _drop_column_if_exists("tickets", "ai_sub_category")
    _drop_column_if_exists("tickets", "ai_category")
