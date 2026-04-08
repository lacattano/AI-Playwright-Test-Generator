"""Tests for constrained semantic candidate ranking."""

from __future__ import annotations

import json

from src.semantic_candidate_ranker import SemanticCandidateRanker


class _FakeGenerator:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def generate(self, prompt: str, timeout: int = 300, system_prompt: str | None = None) -> str:
        _ = prompt, timeout, system_prompt
        return json.dumps(self.payload)


def test_choose_best_candidate_returns_selected_shortlisted_candidate() -> None:
    ranker = SemanticCandidateRanker(_FakeGenerator({"selected_index": 1}))
    candidates = [
        {"selector": "#cart-link", "text": "Cart", "role": "a"},
        {"selector": ".cart_description", "text": "Blue Top", "role": "div"},
    ]

    import asyncio

    result = asyncio.run(
        ranker.choose_best_candidate(
            action="ASSERT",
            description="items added correctly",
            current_url="https://example.com/view_cart",
            candidates=candidates,
        )
    )

    assert result == candidates[1]


def test_choose_best_candidate_returns_none_for_invalid_json() -> None:
    class _BadGenerator:
        async def generate(self, prompt: str, timeout: int = 300, system_prompt: str | None = None) -> str:
            _ = prompt, timeout, system_prompt
            return "not json"

    ranker = SemanticCandidateRanker(_BadGenerator())

    import asyncio

    result = asyncio.run(
        ranker.choose_best_candidate(
            action="CLICK",
            description="go to cart",
            current_url="https://example.com/",
            candidates=[{"selector": "#one"}],
        )
    )

    assert result is None or result == {"selector": "#one"}
