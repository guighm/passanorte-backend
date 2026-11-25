"""Add discovery fields and initialize the documented catalog categories."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_catalog_s3"
down_revision = "20261123_catalog_s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tourist_spots", sa.Column("address", sa.String(500)), schema="catalog")
    op.add_column("tourist_spots", sa.Column("image_url", sa.String(2048)), schema="catalog")
    op.add_column("tourist_spots", sa.Column("duration_minutes", sa.Integer()), schema="catalog")
    op.add_column("events", sa.Column("ends_at", sa.DateTime()), schema="catalog")
    op.execute("""
        INSERT INTO catalog.categories (id, name, is_active)
        SELECT md5('passanorte:category:' || name), name, true
        FROM (VALUES ('Lazer'), ('Cultura'), ('Gastronomia')) AS official(name)
        WHERE NOT EXISTS (SELECT 1 FROM catalog.categories WHERE lower(categories.name) = lower(official.name))
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_column("events", "ends_at", schema="catalog")
    for name in ("duration_minutes", "image_url", "address"):
        op.drop_column("tourist_spots", name, schema="catalog")
