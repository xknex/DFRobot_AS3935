# Feature: as3935-modernization, Property 8: Post-close methods raise RuntimeError
"""Property-based test verifying that _ensure_open() raises RuntimeError
after close() has been called, and that close() can be called multiple
times without raising.

**Validates: Requirements 3.5**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from dfrobot_as3935.sensor import DFRobot_AS3935


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Number of times to call _ensure_open after close
_num_calls = st.integers(min_value=1, max_value=5)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestPostCloseRaisesRuntimeError:
    """Property 8: Post-close methods raise RuntimeError.

    For any number of _ensure_open() calls after close() has been called,
    each call SHALL raise a RuntimeError indicating the resource has been
    closed.
    """

    @given(num_methods=_num_calls)
    @settings(max_examples=100)
    def test_ensure_open_raises_after_close(self, num_methods: int) -> None:
        """_ensure_open() raises RuntimeError after close() for any number of calls."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = 0x00

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act: close the sensor
        sensor.close()

        # Assert: each _ensure_open() call raises RuntimeError
        for _ in range(num_methods):
            with pytest.raises(RuntimeError, match="closed"):
                sensor._ensure_open()

    @given(num_methods=_num_calls)
    @settings(max_examples=100)
    def test_close_multiple_times_does_not_raise(self, num_methods: int) -> None:
        """Calling close() multiple times after the first does not raise."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = 0x00

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act & Assert: first close and subsequent closes do not raise
        for _ in range(num_methods + 1):
            sensor.close()  # Should never raise
