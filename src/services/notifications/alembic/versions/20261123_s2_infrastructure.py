"""Install durable messaging tables for notifications."""
from alembic import op

from shared.delivery import inbox_table, outbox_table

revision = "20261123_notifications_s2"
down_revision = 'eb2efbf47c56'
branch_labels = None
depends_on = None


def upgrade() -> None:
    outbox_table("notifications").create(op.get_bind())
    inbox_table("notifications").create(op.get_bind())


def downgrade() -> None:
    inbox_table("notifications").drop(op.get_bind())
    outbox_table("notifications").drop(op.get_bind())
