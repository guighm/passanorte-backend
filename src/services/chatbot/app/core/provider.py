"""Camada abstrata de provider de LLM (D-08) — T061.

Providers: `stub` (default, determinístico), `gemini` (Google Gemini free tier)
e `ollama` (local). Indisponibilidade levanta `ProviderUnavailable`, mapeada
para `assistant_unavailable` (503) — nunca roteiro inventado (RF38).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class ProviderUnavailable(Exception):
    """LLM indisponível (timeout, cota, rede) — responde 503 ao turista (D-08)."""


class LLMProvider(ABC):
    """Contrato de geração: prompt restrito ao contexto recuperado (RF38)."""

    name: str

    @abstractmethod
    def generate(self, *, question: str, context: list[dict]) -> str:
        """Responde restringido ao `context` (conteúdo recuperado do catálogo)."""


class StubProvider(LLMProvider):
    """Default (D-08): monta o roteiro determinístico a partir do contexto — não alucina."""

    name = "stub"

    def generate(self, *, question: str, context: list[dict]) -> str:
        if not context:
            return (
                "Não encontrei pontos turísticos indexados para o seu pedido. "
                "Tente pedir por outro tema (ex.: museus, teatros, natureza)."
            )
        lines = ["Sugestão de roteiro com base no catálogo oficial:"]
        total = 0.0
        for item in context:
            entry = f"- {item['title']}"
            if item.get("ticket_price"):
                total += item["ticket_price"]
                entry += f" (ingresso R$ {item['ticket_price']:.2f})"
            if item.get("schedule_text"):
                entry += f" — horário: {item['schedule_text']}"
            elif item.get("occurs_at"):
                entry += f" — ocorre em {item['occurs_at']}"
            if item.get("status") != "open":
                entry += f" — ATENÇÃO: {item['status'].replace('_', ' ')}"
            lines.append(entry)
        lines.append(f"Custo total estimado dos ingressos: R$ {total:.2f}")
        return "\n".join(lines)


class GeminiProvider(LLMProvider):
    """Google Gemini free tier via REST (D-08); exige LLM_GEMINI_API_KEY."""

    name = "gemini"

    def generate(self, *, question: str, context: list[dict]) -> str:
        import json as _json

        import httpx

        api_key = os.environ.get("LLM_GEMINI_API_KEY", "")
        if not api_key:
            raise ProviderUnavailable("LLM_GEMINI_API_KEY não configurada")
        prompt = (
            "Você é o assistente de turismo PassaNorte. Responda em português, "
            "usando SOMENTE os itens do contexto a seguir (nunca invente pontos).\n"
            f"Contexto: {_json.dumps(context, ensure_ascii=False)}\n"
            f"Pedido do turista: {question}"
        )
        try:
            resp = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise ProviderUnavailable(str(exc)) from None


class OllamaProvider(LLMProvider):
    """Ollama local (D-08); modelo configurável via LLM_OLLAMA_MODEL."""

    name = "ollama"

    def generate(self, *, question: str, context: list[dict]) -> str:
        import json as _json

        import httpx

        base_url = os.environ.get("LLM_OLLAMA_URL", "http://localhost:11434")
        model = os.environ.get("LLM_OLLAMA_MODEL", "llama3.1")
        prompt = (
            "Você é o assistente de turismo PassaNorte. Responda em português, "
            "usando SOMENTE os itens do contexto a seguir (nunca invente pontos).\n"
            f"Contexto: {_json.dumps(context, ensure_ascii=False)}\n"
            f"Pedido do turista: {question}"
        )
        try:
            resp = httpx.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except (httpx.HTTPError, KeyError) as exc:
            raise ProviderUnavailable(str(exc)) from None


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "stub": StubProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def get_provider() -> LLMProvider:
    """Provider ativo pela variável LLM_PROVIDER (default `stub`, D-08)."""
    name = os.environ.get("LLM_PROVIDER", "stub").lower()
    return _PROVIDERS.get(name, StubProvider)()
