"""Smoke tests for fact extraction. Skipped if no OPENAI_API_KEY."""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")
def test_extract_facts_basic():
    from company_brain.extraction import extract_facts

    facts = extract_facts(
        "On 2024-11-12 Roey met with Michal to scope the new sales lakehouse. "
        "They decided the fact_orders table will join customers on customer_id."
    )
    assert isinstance(facts, list)
    assert len(facts) >= 1
    for f in facts:
        assert f.fact
        assert 0.0 <= f.confidence <= 1.0
        assert f.type in {
            "schema",
            "relationship",
            "event",
            "preference",
            "decision",
            "todo",
            "knowledge",
        }
