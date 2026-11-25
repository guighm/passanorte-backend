"""Install durable messaging tables for catalog."""
from alembic import op

import sqlalchemy as sa

from shared.delivery import inbox_table, outbox_table

revision = "20261123_catalog_s2"
down_revision = '337f7332c9c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("prize_id", sa.String(36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        schema="catalog",
    )
    op.create_table(
        "route_points",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("catalog.routes.id"), nullable=False),
        sa.Column("tourist_spot_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        schema="catalog",
    )
    op.create_index("ix_route_points_route_id", "route_points", ["route_id"], schema="catalog")
    outbox_table("catalog").create(op.get_bind())
    inbox_table("catalog").create(op.get_bind())


def downgrade() -> None:
    op.drop_table("route_points", schema="catalog")
    op.drop_table("routes", schema="catalog")
    inbox_table("catalog").drop(op.get_bind())
    outbox_table("catalog").drop(op.get_bind())
