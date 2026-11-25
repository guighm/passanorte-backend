"""Store tourist logins separately from platform accesses."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_insights_s3"
down_revision = "20261123_insights_s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tourist_logins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        schema="insights",
    )
    op.create_index("ix_tourist_logins_user_id", "tourist_logins", ["user_id"], schema="insights")


def downgrade() -> None:
    op.drop_table("tourist_logins", schema="insights")
