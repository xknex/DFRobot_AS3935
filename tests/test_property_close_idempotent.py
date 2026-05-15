# Feature: as3935-modernization, Property 7: close() is idempotent
"""Property-based test verifying that close() can be called multiple times
without raising an exception on any call after the first.

**Validates: Requirements 3.4**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from dfrobot_as3935.sensor import DFRobot_AS3935


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Number of consecutive close() calls (1–10)
_num_calls = st.integers(min_value=1, max_value=10)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestCloseIdempotent:
    """Property 7: close() is idempotent.

    For any number of consecutive close() calls (1 or more) on a sensor
    instance, no call after the first SHALL raise an exception.
    """

    @given(num_calls=_num_calls)
    @settings(max_examples=100)
    def test_close_multiple_times_no_exception(self, num_calls: int) -> None:
        """Calling close() num_calls times raises no exception on any call."""
        # Arrange: create sensor with mocked bus and GPIO
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)

        # Act & Assert: call close() num_calls times, no exception on any call
        for _ in range(num_calls):
            sensor.close()  # Should not raise
