"""Persistent refresh sessions (S1)."""
from alembic import op
import sqlalchemy as sa

revision = "20261123_refresh"
down_revision = "e8b2e20bb374"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_sessions",
        sa.Column("jti_hash", sa.String(64), primary_key=True),
        sa.Column("family_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])


def downgrade():
    op.drop_table("refresh_sessions")
