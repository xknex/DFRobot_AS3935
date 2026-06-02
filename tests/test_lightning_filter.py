"""Tests for near/weak lightning classification."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lightning_collector.collector import _is_near_weak_lightning


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(energy=st.floats(min_value=0.0, max_value=0.2999, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_unconverged_distance_bypasses_filter(energy: float) -> None:
    """Unconverged distance (distance == 1) should bypass the near/weak filter.

    The AS3935 reports distance = 1 km as its unconverged default when the
    internal distance algorithm has not accumulated enough strikes. This is NOT
    a real proximity measurement, so the filter must not apply.

    **Validates: Requirements 2.1, 2.3**
    """
    result = _is_near_weak_lightning(1, energy, 5, 0.25, unconverged_min_energy=0.30)
    assert result is False, (
        f"_is_near_weak_lightning(1, {energy}, 5, 0.25, unconverged_min_energy=0.30) returned True — "
        f"unconverged distance should bypass filter"
    )


@pytest.mark.property
@given(
    distance=st.integers(min_value=2, max_value=5),
    energy=st.floats(min_value=0.0, max_value=0.2499, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_converged_near_weak_preserved(distance: int, energy: float) -> None:
    """Converged near distance with weak energy returns True (filter applies).

    For converged distances (2–5 km) and energy below the threshold (< 0.25),
    the filter correctly identifies near/weak lightning. This behavior must be
    preserved after the unconverged-distance fix.

    **Validates: Requirements 3.1, 3.2, 3.5**
    """
    result = _is_near_weak_lightning(distance, energy, 5, 0.25)
    assert result is True, (
        f"_is_near_weak_lightning({distance}, {energy}, 5, 0.25) returned False — "
        f"converged near/weak should be classified as True"
    )


@pytest.mark.property
@given(
    distance=st.integers(min_value=2, max_value=5),
    energy=st.floats(min_value=0.25, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_converged_near_strong_preserved(distance: int, energy: float) -> None:
    """Converged near distance with strong energy returns False (filter does not apply).

    For converged distances (2–5 km) and energy at or above the threshold (>= 0.25),
    the filter does not classify as near/weak. This behavior must be preserved.

    **Validates: Requirements 3.1, 3.2, 3.5**
    """
    result = _is_near_weak_lightning(distance, energy, 5, 0.25)
    assert result is False, (
        f"_is_near_weak_lightning({distance}, {energy}, 5, 0.25) returned True — "
        f"converged near/strong should be classified as False"
    )


@pytest.mark.property
@given(
    distance=st.integers(min_value=6, max_value=63),
    energy=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_distant_lightning_preserved(distance: int, energy: float) -> None:
    """Distant lightning (distance > 5 km) always returns False.

    For distances beyond the near threshold (> 5 km), the filter never applies
    regardless of energy level. This behavior must be preserved.

    **Validates: Requirements 3.1, 3.2, 3.5**
    """
    result = _is_near_weak_lightning(distance, energy, 5, 0.25)
    assert result is False, (
        f"_is_near_weak_lightning({distance}, {energy}, 5, 0.25) returned True — "
        f"distant lightning should not be classified as near/weak"
    )


@pytest.mark.property
@given(
    energy=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_none_distance_preserved(energy: float) -> None:
    """None distance always returns False (filter cannot apply without distance).

    When distance is None, the filter has insufficient data and returns False.
    This behavior must be preserved.

    **Validates: Requirements 3.1, 3.2, 3.5**
    """
    result = _is_near_weak_lightning(None, energy, 5, 0.25)
    assert result is False, (
        f"_is_near_weak_lightning(None, {energy}, 5, 0.25) returned True — "
        f"None distance should always return False"
    )


@pytest.mark.property
@given(
    distance=st.integers(min_value=2, max_value=63),
)
@settings(max_examples=200)
def test_none_energy_preserved(distance: int) -> None:
    """None energy always returns False (filter cannot apply without energy).

    When energy is None, the filter has insufficient data and returns False.
    This behavior must be preserved.

    **Validates: Requirements 3.1, 3.2, 3.5**
    """
    result = _is_near_weak_lightning(distance, None, 5, 0.25)
    assert result is False, (
        f"_is_near_weak_lightning({distance}, None, 5, 0.25) returned True — "
        f"None energy should always return False"
    )


# ---------------------------------------------------------------------------
# Example-based unit tests
# ---------------------------------------------------------------------------


def test_filters_near_weak_lightning() -> None:
    assert not _is_near_weak_lightning(1, 0.2144, 5, 0.25, unconverged_min_energy=0.30)  # distance=1 with low energy bypasses filter
    assert not _is_near_weak_lightning(1, 0.24, 5, 0.25, unconverged_min_energy=0.30)   # distance=1 with energy < 0.30 bypasses filter
    assert _is_near_weak_lightning(5, 0.0728, 5, 0.25)


def test_allows_near_strong_lightning() -> None:
    assert not _is_near_weak_lightning(1, 0.25, 5, 0.25, unconverged_min_energy=0.30)  # distance=1 with energy < 0.30 bypasses filter
    assert not _is_near_weak_lightning(1, 0.30, 5, 0.25, unconverged_min_energy=0.30)  # distance=1 with energy >= 0.30 is filtered
    assert not _is_near_weak_lightning(5, 0.8, 5, 0.25)


def test_allows_distant_weak_lightning() -> None:
    assert not _is_near_weak_lightning(6, 0.01, 5, 0.25)
    assert not _is_near_weak_lightning(20, 0.04, 5, 0.25)


def test_allows_incomplete_lightning_data() -> None:
    assert not _is_near_weak_lightning(None, 0.01, 5, 0.25, unconverged_min_energy=0.30)
    assert not _is_near_weak_lightning(1, None, 5, 0.25, unconverged_min_energy=0.30)