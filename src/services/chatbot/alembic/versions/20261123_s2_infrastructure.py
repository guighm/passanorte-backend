"""Install durable messaging tables for chatbot."""
from alembic import op

from shared.delivery import inbox_table, outbox_table

revision = "20261123_chatbot_s2"
down_revision = 'be17196c796d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    outbox_table("chatbot").create(op.get_bind())
    inbox_table("chatbot").create(op.get_bind())


def downgrade() -> None:
    inbox_table("chatbot").drop(op.get_bind())
    outbox_table("chatbot").drop(op.get_bind())
