"""AuditLog do serviço gamification (rotas/prizes/desbloqueios) — RNF19, D-09.

Reexporta o modelo compartilhado: cada serviço tem seu próprio banco,
mas o metadado é único no monorepo.
"""

from shared.audit_model import AuditLog  # noqa: F401