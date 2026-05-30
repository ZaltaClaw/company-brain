"""LLM-powered fact extraction.

Takes raw text (an email, a Teams message, a Fabric table description, a Foundry
doc chunk) and returns a list of atomic facts with confidence + temporal markers.
Uses OpenAI's structured-output / response_format=json_schema for determinism.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

FactType = Literal[
    "schema",        # data shape / column / table / FK
    "relationship",  # entity-to-entity link
    "event",         # something that happened at a time
    "preference",    # user/team preference or convention
    "decision",      # decision recorded
    "todo",          # pending action
    "knowledge",     # general knowledge fact
]


class Fact(BaseModel):
    fact: str = Field(description="A single atomic statement, self-contained.")
    confidence: float = Field(ge=0.0, le=1.0)
    temporal_validity: str = Field(
        description="ISO date, ISO range, or 'ongoing' if persistently true."
    )
    type: FactType


class FactList(BaseModel):
    facts: list[Fact]


SYSTEM_PROMPT = """You extract atomic, durable facts from raw enterprise text
(emails, chat, documents, table schemas). Rules:

1. Each fact must stand alone — no pronouns, no "this" / "the document".
2. Prefer specific over general. Names, dates, IDs, numbers are gold.
3. Set confidence < 0.7 if the source is speculative ("I think", "maybe").
4. temporal_validity: use the date the fact was true; 'ongoing' for stable facts
   like schemas, org structure, preferences.
5. Skip pleasantries, signatures, footers, marketing copy.
6. Skip facts that are private to a single sentence and have no reuse value.
"""

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=20))
def extract_facts(text: str, *, context: str | None = None) -> list[Fact]:
    """Extract atomic facts from text. Empty list if nothing useful."""
    if not text or not text.strip():
        return []

    user = text if not context else f"Context: {context}\n\n---\n{text}"
    model = os.getenv("OPENAI_EXTRACT_MODEL", "gpt-4o-mini")

    resp = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "FactList",
                "schema": FactList.model_json_schema(),
                "strict": False,
            },
        },
        temperature=0.0,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        parsed = FactList.model_validate_json(content)
    except Exception:
        # Defensive: some models wrap output. Try to recover.
        data = json.loads(content)
        parsed = FactList.model_validate(data)
    return parsed.facts
