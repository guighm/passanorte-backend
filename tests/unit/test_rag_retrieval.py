"""T058 [US7] Testes unitários da recuperação RAG (RF38/RF39, SC-009).

Apenas conteúdo indexado é recuperado; spots fechados são excluídos/sinalizados.
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")

from services.chatbot.app.core import retrieval as retrieval_mod  # noqa: E402
from services.chatbot.app.core.embeddings import _stub_embed  # noqa: E402
from services.chatbot.app.models.embedding import EmbeddedContent  # noqa: E402


def _index(db, **kwargs):
    db.add(EmbeddedContent(embedding=_stub_embed([kwargs["text_chunk"]])[0], embedded_at=None, **kwargs))
    db.flush()


def test_only_indexed_content_is_retrieved(db_session):
    _index(
        db_session,
        source_type="tourist_spot",
        source_id="s-1",
        spot_id="s-1",
        title="Teatro Amazonas",
        text_chunk="Teatro Amazonas teatro histórico centro de Manaus",
        status="open",
        latitude=-3.47,
        longitude=-60.02,
    )
    results = retrieval_mod.retrieve(
        db_session,
        _stub_embed,
        "roteiro pelo teatro histórico de Manaus",
        top_k=3,
    )
    assert len(results) == 1
    assert results[0].source_id == "s-1"
    # nada indexado para outros temas → vazio
    other = retrieval_mod.retrieve(db_session, _stub_embed, "praia e sol", top_k=3)
    assert other == []


def test_closed_spots_are_flagged_not_recommended(db_session):
    _index(
        db_session,
        source_type="tourist_spot",
        source_id="s-closed",
        spot_id="s-closed",
        title="Cine Rex",
        text_chunk="Cine Rex cinema histórico",
        status="permanently_closed",
        latitude=-3.47,
        longitude=-60.02,
    )
    _index(
        db_session,
        source_type="tourist_spot",
        source_id="s-open",
        spot_id="s-open",
        title="Museu",
        text_chunk="Museu cinema arte história",
        status="open",
        latitude=-3.47,
        longitude=-60.02,
    )
    results = retrieval_mod.retrieve(db_session, _stub_embed, "cinema e história", top_k=5)
    by_id = {r.source_id: r for r in results}
    # fechado é sinalizado, nunca apresentado como opção do roteiro (RF38)
    assert by_id["s-closed"].status == "permanently_closed"
    assert by_id["s-open"].status == "open"
    available = retrieval_mod.retrieve_available(db_session, _stub_embed, "cinema e história")
    assert [r.source_id for r in available] == ["s-open"]


def test_retrieval_ignores_unrelated_content_and_respects_limit(db_session):
    for i in range(5):
        _index(
            db_session,
            source_type="tourist_spot",
            source_id=f"s-{i}",
            spot_id=f"s-{i}",
            title=f"Ponto {i}",
            text_chunk=f"Ponto turístico {i} praia",
            status="open",
            latitude=-3.0 + i,
            longitude=-60.0,
        )
    results = retrieval_mod.retrieve_available(db_session, _stub_embed, "praia", top_k=2)
    assert len(results) == 2
