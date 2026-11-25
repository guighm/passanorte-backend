"""Install durable messaging tables for benefits."""
from alembic import op

from services.benefits.app.models import LedgerEntry
from shared.delivery import inbox_table, outbox_table

revision = "20261123_benefits_s2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    LedgerEntry.__table__.create(op.get_bind())
    outbox_table("benefits").create(op.get_bind())
    inbox_table("benefits").create(op.get_bind())


def downgrade() -> None:
    LedgerEntry.__table__.drop(op.get_bind())
    inbox_table("benefits").drop(op.get_bind())
    outbox_table("benefits").drop(op.get_bind())
