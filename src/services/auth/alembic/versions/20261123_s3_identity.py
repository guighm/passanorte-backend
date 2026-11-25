"""Migrate panel identities without changing historical actor IDs."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_auth_s3"
down_revision = "20261123_auth_s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("partner_id", sa.String(36)), schema="auth")
    op.create_index("ix_users_partner_id", "users", ["partner_id"], schema="auth")
    op.execute("""
        INSERT INTO auth.audit_logs (id, actor_id, action, entity, entity_id, occurred_at)
        SELECT md5('s3-unlinked:' || id), id, 'supplier_missing_partner_s3', 'users', id, now()
        FROM auth.users WHERE role = 'employee'
    """)
    op.execute("""
        UPDATE auth.refresh_sessions SET revoked = true
        WHERE user_id IN (SELECT id FROM auth.users WHERE role = 'employee')
    """)
    op.execute("UPDATE auth.users SET is_active = false WHERE role = 'employee'")
    op.execute("ALTER TYPE auth.user_role RENAME VALUE 'employee' TO 'supplier'")
    op.create_check_constraint("ck_active_supplier_partner", "users",
                               "role != 'supplier' OR partner_id IS NOT NULL OR NOT is_active", schema="auth")
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True, schema="auth")
    op.create_index("uq_users_normalized_document", "users", [sa.text("coalesce(cpf_hash, passport_hash)")],
                    unique=True, schema="auth")
    op.add_column("tourist_profiles", sa.Column("consent_version", sa.String(40)), schema="auth")
    op.add_column("tourist_profiles", sa.Column("consent_at", sa.DateTime(timezone=True)), schema="auth")


def downgrade() -> None:
    raise RuntimeError("Restore the S2 backup to reverse the identity migration.")
