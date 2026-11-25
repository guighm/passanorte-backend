"""Install durable messaging tables for gamification."""
from alembic import op

from services.validation.app.models.visit import Visit
from shared.delivery import inbox_table, outbox_table

revision = "20261123_gamification_s2"
down_revision = 'f3a4b1c2d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT FROM gamification.routes) THEN
            RAISE EXCEPTION 'Import legacy routes through scripts/migrate_legacy.py into a clean S2 database';
        END IF;
    END $$""")
    op.drop_constraint("route_enrollments_route_id_fkey", "route_enrollments", type_="foreignkey")
    op.drop_table("route_points")
    op.drop_table("routes")
    Visit.__table__.create(op.get_bind())
    outbox_table("gamification").create(op.get_bind())
    inbox_table("gamification").create(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Restore the pre-S2 backup to roll back the domain split.")
