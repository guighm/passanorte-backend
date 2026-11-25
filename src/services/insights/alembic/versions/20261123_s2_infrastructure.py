"""Install durable messaging tables for insights."""
from alembic import op

from shared.delivery import inbox_table, outbox_table

revision = "20261123_insights_s2"
down_revision = 'c81e4d75db36'
branch_labels = None
depends_on = None


def upgrade() -> None:
    outbox_table("insights").create(op.get_bind())
    inbox_table("insights").create(op.get_bind())


def downgrade() -> None:
    inbox_table("insights").drop(op.get_bind())
    outbox_table("insights").drop(op.get_bind())
