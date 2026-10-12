"""Helper de render_item do Alembic autogenerate.

Sem customização, o Alembic renderiza um TypeDecorator pelo caminho completo do
módulo (ex.: `services.chatbot.app.models.embedding.EmbeddingType()`) mas NÃO
emite o `import` correspondente — a migração gerada quebra no `upgrade` com
NameError. Este renderer adiciona o import no arquivo gerado.
"""
from __future__ import annotations

from alembic.autogenerate.api import AutogenContext
from sqlalchemy.types import TypeDecorator


def render_item_with_custom_types(
    type_: str, obj: object, autogen_context: AutogenContext
) -> str | bool:
    """Renderiza tipos customizados (TypeDecorator) emitindo o import do módulo.

    Retorna False para renderização padrão do Alembic nos demais casos.
    """
    if type_ == "type" and isinstance(obj, TypeDecorator):
        class_ = type(obj)
        module = class_.__module__
        if not module.startswith("sqlalchemy"):
            autogen_context.imports.add(f"import {module}")
            return f"{module}.{class_.__name__}()"
    return False
