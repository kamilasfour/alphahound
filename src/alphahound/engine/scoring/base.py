"""Scorer interface — the contract every scoring backend implements.

Sprint 3: one concrete backend (FinBERTScorer, CPU).
Sprint 5+: RunPodScorer slots in here, same interface, zero changes upstream.

Design:
  - Scorer.score_batch() is the only method callers use.
  - Input: list of raw text strings.
  - Output: list of SentimentScore named tuples (polarity, confidence).
  - Polarity: float in [-1, 1].  Negative = bearish, positive = bullish.
  - Confidence: float in [0, 1]. How certain the model is.

The caller (orchestrator.py) never imports a concrete backend directly.
It imports get_scorer() which returns whatever backend is configured
via the ALPHAHOUND_SCORER env var. Default: 'finbert'.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple


class SentimentScore(NamedTuple):
    polarity: float    # [-1, 1]  negative=bearish, positive=bullish
    confidence: float  # [0, 1]   how certain the model is


class BaseScorer(ABC):
    """Every scoring backend subclasses this."""

    @abstractmethod
    def score_batch(self, texts: list[str]) -> list[SentimentScore]:
        """Score a batch of texts. Returns one SentimentScore per text.

        Implementations must:
        - Return results in the same order as input texts.
        - Never raise on individual bad inputs — return SentimentScore(0.0, 0.0) instead.
        - Be thread-safe (the orchestrator may call from multiple threads later).
        """
        ...

    def score_one(self, text: str) -> SentimentScore:
        """Convenience wrapper for single-text scoring."""
        results = self.score_batch([text])
        return results[0]


def get_scorer(backend: str | None = None) -> BaseScorer:
    """Factory — returns the configured scorer backend.

    Backend options (set via ALPHAHOUND_SCORER env var or pass directly):
        'finbert'  (default) — local FinBERT on CPU
        'runpod'             — RunPod Serverless (Sprint 5+, not yet implemented)

    Usage:
        scorer = get_scorer()           # reads ALPHAHOUND_SCORER env var
        scorer = get_scorer('finbert')  # explicit
    """
    import os
    backend = backend or os.environ.get("ALPHAHOUND_SCORER", "finbert")

    if backend == "finbert":
        from alphahound.engine.scoring.finbert import FinBERTScorer
        return FinBERTScorer()

    if backend == "runpod":
        raise NotImplementedError(
            "RunPod scorer is planned for Sprint 5. "
            "Set ALPHAHOUND_SCORER=finbert or leave unset."
        )

    raise ValueError(
        f"Unknown scorer backend '{backend}'. "
        f"Valid options: finbert. (runpod coming in Sprint 5)"
    )
