"""AuditLog do serviço catalog (pontos/eventos/categorias) — RNF19, T026.

Reexporta o modelo compartilhado: cada serviço tem seu próprio banco,
mas o metadado é único no monorepo.
"""

from shared.audit_model import AuditLog  # noqa: F401
