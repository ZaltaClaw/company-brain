"""OpenAI embeddings wrapper with batching + retries."""

from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _model() -> str:
    return os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def _embed_batch(inputs: list[str]) -> list[list[float]]:
    resp = _get_client().embeddings.create(model=_model(), input=inputs)
    return [d.embedding for d in resp.data]


def embed(texts: Iterable[str], *, batch_size: int = 100) -> list[list[float]]:
    """Embed an iterable of strings. Empty strings are mapped to zero vectors."""
    items = [t if t and t.strip() else " " for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(items), batch_size):
        out.extend(_embed_batch(items[i : i + batch_size]))
    return out


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
