"""AI triage for customer tickets using OpenAI Codex models."""
from __future__ import annotations

import json

from app.core.config import settings


def normalize_confidence(value: object) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if isinstance(value, str):
        cleaned = value.strip().lower()
        mapping = {
            "low": 25,
            "baixa": 25,
            "medium": 60,
            "media": 60,
            "média": 60,
            "high": 85,
            "alta": 85,
        }
        if cleaned in mapping:
            return mapping[cleaned]
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        if digits:
            return max(0, min(100, int(digits)))
    return 0


def normalize_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(f"- {item}" for item in parts) or None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or None


async def analyze_ticket_with_ai(ticket_context: dict) -> dict:
    if not settings.OPENAI_API_KEY:
        return {"status": "unavailable", "reason": "OPENAI_API_KEY not configured"}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = f"""
Voce e um analista senior de suporte e observabilidade.
Analise o ticket abaixo e devolva JSON puro com as chaves:
summary, suspected_cause, recommended_actions, confidence.
confidence deve ser um numero inteiro de 0 a 100.

Ticket:
{json.dumps(ticket_context, ensure_ascii=False, indent=2)}
"""
        response = client.responses.create(
            model=settings.OPENAI_CODEX_MODEL,
            reasoning={"effort": "medium"},
            input=prompt,
        )
        output_text = getattr(response, "output_text", "") or "{}"
        data = json.loads(output_text)
        return {
            "status": "completed",
            "summary": normalize_text(data.get("summary")),
            "suspected_cause": normalize_text(data.get("suspected_cause")),
            "recommended_actions": normalize_text(data.get("recommended_actions")),
            "confidence": normalize_confidence(data.get("confidence", 0)),
            "model": settings.OPENAI_CODEX_MODEL,
            "raw": {"output_text": output_text},
        }
    except Exception as exc:  # pragma: no cover - external API
        return {"status": "failed", "reason": str(exc)}
