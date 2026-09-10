"""Unit tests for the velocity signal math.

We only test `_compute_velocity` \u2014 the DB-touching `compute_and_store_all`
and `compute_for_entity` need integration tests (Sprint 4 territory).
"""
from __future__ import annotations

import pytest

from alphahound.engine.signals.velocity import _compute_velocity


def test_no_history_zero_posts():
    """Cold start: no 7d history, no current posts -> neutral signal."""
    velocity, signal, confidence = _compute_velocity(posts_1h=0, posts_7d=0)
    assert velocity == 0.0
    assert signal == 5.0  # midpoint
    assert confidence == 1.0  # very low


def test_no_history_burst():
    """Cold start with a burst of posts \u2014 velocity is raw count, confidence stays low."""
    velocity, signal, confidence = _compute_velocity(posts_1h=5, posts_7d=0)
    assert velocity == 5.0
    assert signal == 10.0  # clamped
    assert confidence == 1.0


def test_posting_at_baseline():
    """7d gives ~10 posts/hour; current hour has 10 posts -> velocity 0."""
    # baseline = 1680 / 168 = 10 posts/hour
    velocity, signal, confidence = _compute_velocity(posts_1h=10, posts_7d=1680)
    assert velocity == pytest.approx(0.0)
    assert signal == pytest.approx(5.0)
    assert confidence > 5.0  # lots of data = confident


def test_posting_at_2x_baseline():
    """Current hour is 2x baseline -> velocity 1 -> signal 6.5."""
    velocity, signal, _ = _compute_velocity(posts_1h=20, posts_7d=1680)
    assert velocity == pytest.approx(1.0)
    assert signal == pytest.approx(6.5)


def test_posting_at_3x_baseline_bumps_signal():
    """3x baseline -> signal 8."""
    velocity, signal, _ = _compute_velocity(posts_1h=30, posts_7d=1680)
    assert velocity == pytest.approx(2.0)
    assert signal == pytest.approx(8.0)


def test_posting_below_baseline_lowers_signal():
    """Half baseline -> velocity -0.5 -> signal 4.25."""
    velocity, signal, _ = _compute_velocity(posts_1h=5, posts_7d=1680)
    assert velocity == pytest.approx(-0.5)
    assert signal == pytest.approx(4.25)


def test_signal_is_clamped_to_1_10_range():
    """Extreme velocity can't push signal out of [1, 10]."""
    # 100x baseline: velocity=99, raw signal=5+99*1.5=153.5, clamped to 10
    _, signal_high, _ = _compute_velocity(posts_1h=1000, posts_7d=1680)
    assert signal_high == 10.0

    # 1/1000 baseline: very low velocity, clamped to 1
    _, signal_low, _ = _compute_velocity(posts_1h=0, posts_7d=168_000)
    assert signal_low >= 1.0
    assert signal_low < 5.0


def test_confidence_saturates():
    """Confidence is capped at 10 even for huge 7d counts."""
    _, _, confidence = _compute_velocity(posts_1h=100, posts_7d=1_000_000)
    assert confidence == 10.0


def test_confidence_scales_with_sample_size():
    """More 7d data should mean higher confidence."""
    _, _, low = _compute_velocity(posts_1h=1, posts_7d=20)
    _, _, high = _compute_velocity(posts_1h=1, posts_7d=500)
    assert high > low
