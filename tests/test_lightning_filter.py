"""Tests for near/weak lightning classification."""

from lightning_collector.collector import _is_near_weak_lightning


def test_filters_near_weak_lightning() -> None:
    assert _is_near_weak_lightning(1, 0.2144, 5, 0.25)
    assert _is_near_weak_lightning(5, 0.0728, 5, 0.25)


def test_allows_near_strong_lightning() -> None:
    assert not _is_near_weak_lightning(1, 0.25, 5, 0.25)
    assert not _is_near_weak_lightning(5, 0.8, 5, 0.25)


def test_allows_distant_weak_lightning() -> None:
    assert not _is_near_weak_lightning(6, 0.01, 5, 0.25)
    assert not _is_near_weak_lightning(20, 0.04, 5, 0.25)


def test_allows_incomplete_lightning_data() -> None:
    assert not _is_near_weak_lightning(None, 0.01, 5, 0.25)
    assert not _is_near_weak_lightning(1, None, 5, 0.25)