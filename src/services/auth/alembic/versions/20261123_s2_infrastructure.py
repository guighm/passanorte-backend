"""Install durable messaging tables for auth."""
from alembic import op

from shared.delivery import inbox_table, outbox_table

revision = "20261123_auth_s2"
down_revision = '20261123_refresh'
branch_labels = None
depends_on = None


def upgrade() -> None:
    outbox_table("auth").create(op.get_bind())
    inbox_table("auth").create(op.get_bind())


def downgrade() -> None:
    inbox_table("auth").drop(op.get_bind())
    outbox_table("auth").drop(op.get_bind())
