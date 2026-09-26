"""Serviço de embeddings — D-08: modelo gratuito, fallback determinístico em testes.

Preferência: `sentence-transformers` com modelo multilíngue leve
(`paraphrase-multilingual-MiniLM-L12-v2`). Sem o pacote/modelo em ambiente de
teste, usa um embedder determinístico (hashing bag-of-words) — mesmo contrato
`texts -> list[list[float]]`.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable

Embedder = Callable[[Iterable[str]], list[list[float]]]

_STUB_DIM = 256


def _stub_embed(texts: Iterable[str]) -> list[list[float]]:
    """Embedder determinístico: soma de projeções pseudo-aleatórias por token.

    Cada token gera um vetor denso via SHA-256 (não criptográfico aqui) —
    tokens distintos ficam ~ortogonais, então consultas sem overlap léxico
    têm similaridade ≈ 0.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * _STUB_DIM
        for token in str(text).lower().split():
            data = b"".join(
                hashlib.sha256(f"{token}:{i}".encode()).digest() for i in range(_STUB_DIM // 32 + 1)
            )
            # centrado em zero: tokens distintos ficam ~ortogonais
            signed = [data[j] / 127.5 - 1.0 for j in range(_STUB_DIM)]
            norm = math.sqrt(sum(v * v for v in signed)) or 1.0
            for j in range(_STUB_DIM):
                vec[j] += signed[j] / norm
        n = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / n for v in vec])
    return vectors


def _sentence_transformer_embed() -> Embedder | None:
    """Modelo local gratuito (D-08) quando o pacote e o modelo estão disponíveis."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception:  # noqa: BLE001 — qualquer falha de download/import cai no stub
        return None

    def embed(texts: Iterable[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in model.encode(list(texts), show_progress_bar=False)]

    return embed


def get_embedder() -> Embedder:
    """Retorna o embedder ativo (injetável nos endpoints; testes usam o stub)."""
    return _sentence_transformer_embed() or _stub_embed


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno entre dois vetores (recuperação top-k)."""
    if len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0
