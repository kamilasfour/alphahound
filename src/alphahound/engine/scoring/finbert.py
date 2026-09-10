"""FinBERT scoring backend — CPU inference using ProsusAI/finbert.

Model: ProsusAI/finbert (HuggingFace)
  - Trained on ~10K financial news sentences
  - 3 classes: positive, negative, neutral
  - ~440 MB download, cached to ~/.cache/huggingface/hub/

Polarity formula (PRD v1.2 §A6.1):
    polarity   = prob_positive - prob_negative   # range [-1, 1]
    confidence = max(prob_positive, prob_neutral, prob_negative)

We pin to a specific model revision so upstream changes don't silently
break scoring. Bump the revision intentionally when upgrading.

Lazy loading: the model is downloaded and loaded on first call to
score_batch(), not at import time. This keeps CLI startup fast even
when transformers is installed.
"""
from __future__ import annotations

import os
# Limit PyTorch/FinBERT CPU threads to avoid saturating the machine.
# Full core usage causes 100% CPU spikes during scheduled scoring runs.
# Azure Function migration will remove this constraint entirely.
_cpu_threads = int(os.environ.get("FINBERT_CPU_THREADS", "2"))
try:
    import torch
    torch.set_num_threads(_cpu_threads)
except Exception:
    pass
try:
    import torch
    os.environ.setdefault("OMP_NUM_THREADS", str(_cpu_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(_cpu_threads))
except Exception:
    pass

import logging
from typing import TYPE_CHECKING

from alphahound.engine.scoring.base import BaseScorer, SentimentScore

if TYPE_CHECKING:
    from transformers import Pipeline  # type: ignore

log = logging.getLogger(__name__)

# Pinned revision — bump intentionally when upgrading.
MODEL_NAME = "ProsusAI/finbert"
MODEL_REVISION = "main"  # pin to a commit SHA when we stabilise e.g. "d109f33"

# Batch size for inference. 32 is a sweet spot for CPU — large enough to
# amortise tokenisation overhead, small enough to avoid memory pressure.
DEFAULT_BATCH_SIZE = 32

# FinBERT label order (from model config). Do NOT rely on alphabetical order.
_LABEL_MAP: dict[str, str] = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
    # Some checkpoints use title-case
    "Positive": "positive",
    "Negative": "negative",
    "Neutral": "neutral",
}


class FinBERTScorer(BaseScorer):
    """Scores financial text using ProsusAI/finbert on CPU.

    Thread-safe: the underlying pipeline is stateless per call.
    Lazy-loads model on first use.
    """

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self.batch_size = batch_size
        self._pipeline: "Pipeline | None" = None

    def _get_pipeline(self) -> "Pipeline":
        """Lazy-load the model. Called on first score_batch() call."""
        if self._pipeline is None:
            log.info(
                "Loading FinBERT model '%s' (first call — may take 30–60s on first download)...",
                MODEL_NAME,
            )
            try:
                from transformers import pipeline  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "transformers is not installed. Run: pip install transformers torch"
                ) from exc

            self._pipeline = pipeline(
                task="text-classification",
                model=MODEL_NAME,
                revision=MODEL_REVISION,
                top_k=None,          # return all 3 class probabilities
                truncation=True,
                max_length=512,
                device=-1,           # -1 = CPU (change to 0 for CUDA GPU)
            )
            log.info("FinBERT loaded successfully.")
        return self._pipeline

    def score_batch(self, texts: list[str]) -> list[SentimentScore]:
        """Score a list of texts. Returns SentimentScore per text, in order."""
        if not texts:
            return []

        pipe = self._get_pipeline()
        results: list[SentimentScore] = []

        # Process in batches to control memory.
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            # Sanitise inputs — empty or whitespace-only strings confuse the tokeniser.
            cleaned = [t.strip() if t and t.strip() else "neutral" for t in chunk]
            try:
                raw_outputs = pipe(cleaned)
            except Exception as exc:
                log.warning("FinBERT batch failed for chunk %d: %s", i, exc)
                # Return neutral scores for the whole failed chunk.
                results.extend([SentimentScore(0.0, 0.0)] * len(chunk))
                continue

            for output in raw_outputs:
                score = self._parse_output(output)
                results.append(score)

        return results

    @staticmethod
    def _parse_output(output: list[dict]) -> SentimentScore:
        """Convert FinBERT's [{'label': ..., 'score': ...}] to SentimentScore."""
        try:
            probs: dict[str, float] = {}
            for item in output:
                label = _LABEL_MAP.get(item["label"], "neutral")
                probs[label] = float(item["score"])

            pos = probs.get("positive", 0.0)
            neg = probs.get("negative", 0.0)
            neu = probs.get("neutral", 0.0)

            polarity = round(pos - neg, 6)          # [-1, 1]
            confidence = round(max(pos, neg, neu), 6)  # [0, 1]

            return SentimentScore(polarity=polarity, confidence=confidence)

        except Exception as exc:
            log.warning("FinBERT output parse failed: %s — returning neutral", exc)
            return SentimentScore(0.0, 0.0)
