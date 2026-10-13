"""add shared audit_logs table (tabela faltante: AuditLog compartilhado não
estava registrado no metadata do serviço — create/update/remove_route falhavam
com ProgrammingError UndefinedTable)

Revision ID: f3a4b1c2d5e6
Revises: 7f7cf125d391
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa


revision = 'f3a4b1c2d5e6'
down_revision = '7f7cf125d391'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=True),
    sa.Column('payload_json', sa.String(length=2000), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')