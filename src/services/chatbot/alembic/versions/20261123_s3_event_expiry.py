"""Retain the end time needed to exclude expired catalog events."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_chatbot_s3"
down_revision = "20261123_chatbot_s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("embedded_contents", sa.Column("ends_at", sa.DateTime()), schema="chatbot")


def downgrade() -> None:
    op.drop_column("embedded_contents", "ends_at", schema="chatbot")
