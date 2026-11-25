"""Create the Benefits-owned registry of partner companies."""

from alembic import op

from services.benefits.app.models import Partner, PartnerAuditLog

revision = "20261123_benefits_s3"
down_revision = "20261123_benefits_s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Partner.__table__.create(op.get_bind())
    PartnerAuditLog.__table__.create(op.get_bind())


def downgrade() -> None:
    PartnerAuditLog.__table__.drop(op.get_bind())
    Partner.__table__.drop(op.get_bind())
