# Implementation Plan: AS3935 Library Modernization

## Overview

Modernize the DFRobot AS3935 Lightning Sensor Python library for Raspberry Pi Zero 2W with Python 3.11+ and Raspberry Pi OS Bookworm. Implementation follows a bottom-up approach: package structure and constants first, then validators, sensor class, GPIO integration, examples, and tests.

## Tasks

- [x] 1. Set up package structure and project configuration
  - [x] 1.1 Create pyproject.toml with build system, metadata, and dependencies
    - Define build system backend (setuptools or hatchling)
    - Set project name `dfrobot_as3935`, version, description, license
    - Set `requires-python = ">=3.11"`
    - Declare runtime dependencies: `smbus2` and `gpiozero` with minimum version pins
    - Declare optional test dependencies: `pytest>=7.0`, `hypothesis>=6.0`
    - Configure pytest settings (testpaths, markers)
    - _Requirements: 8.1, 8.3, 8.5, 13.1_

  - [x] 1.2 Create src/dfrobot_as3935/__init__.py with public API exports
    - Import main sensor class and all public constants
    - Define `__all__` listing all exported names
    - Add module-level docstring with library summary, hardware description, and usage example
    - _Requirements: 8.2, 8.4, 7.4_

  - [x] 1.3 Create src/dfrobot_as3935/constants.py with all named constants
    - Define register address constants (REG_AFE_GAIN through REG_CALIB_RCO)
    - Define bitmask constants (MASK_PWD, MASK_AFE_GAIN, MASK_NF_LEV, etc.)
    - Define configuration values (AFE_GAIN_INDOOR=0x24, AFE_GAIN_OUTDOOR=0x1C)
    - Define interrupt source codes (INT_LIGHTNING=0x08, INT_DISTURBER=0x04, INT_NOISE=0x01)
    - Define command bytes (CMD_PRESET_DEFAULT=0x96, CMD_CALIB_RCO=0x96)
    - Define valid parameter sets (VALID_I2C_ADDRESSES, VALID_MIN_STRIKES, VALID_CAPACITANCE_RANGE)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2. Implement input validation module
  - [x] 2.1 Create src/dfrobot_as3935/validators.py with all validation functions
    - Implement `validate_capacitance(value)` — must be int, multiple of 8, range 0–120
    - Implement `validate_noise_floor_level(value)` — must be int, range 0–7
    - Implement `validate_watchdog_threshold(value)` — must be int, range 0–15
    - Implement `validate_spike_rejection(value)` — must be int, range 0–15
    - Implement `validate_i2c_address(value)` — must be in {0x01, 0x02, 0x03}
    - Implement `validate_lco_fdiv(value)` — must be int, range 0–3
    - Implement `validate_min_strikes(value)` — must be in {1, 5, 9, 16}
    - Each validator raises `ValueError` with parameter name, provided value, and valid constraint
    - Add type hints and Google-style docstrings to all functions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.1, 7.3_

  - [x] 2.2 Write property test for input validation rejection (Property 4)
    - **Property 4: Input validation rejects invalid values without I2C writes**
    - Generate out-of-range values for each parameter using Hypothesis strategies
    - Verify ValueError is raised with correct message content
    - Verify no I2C write_byte_data calls occur
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**

  - [x] 2.3 Write property test for input validation acceptance (Property 5)
    - **Property 5: Input validation accepts all valid values**
    - Generate in-range values for each parameter using Hypothesis strategies
    - Verify no ValueError is raised for any valid input
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**

- [x] 3. Implement main sensor class — core I2C operations
  - [x] 3.1 Create src/dfrobot_as3935/sensor.py with class skeleton and I2C methods
    - Define `DFRobot_AS3935` class with `__init__`, type-annotated instance variables
    - Implement `_read_register(register)` using `smbus2.read_byte_data`
    - Implement `_write_register(register, value)` using `smbus2.write_byte_data`
    - Implement `_read_modify_write(register, mask, value)` for bitfield operations
    - Add `threading.RLock` for all I2C access serialization
    - Wrap I2C errors in OSError with register address, device address, and cause
    - Add DEBUG logging for all I2C read/write operations
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.6, 11.1, 11.3, 9.3_

  - [x] 3.2 Write property test for register read (Property 1)
    - **Property 1: Register read returns correct value**
    - Generate valid register addresses and byte values
    - Mock SMBus.read_byte_data to return generated value
    - Verify _read_register returns exact byte value
    - **Validates: Requirements 1.2**

  - [x] 3.3 Write property test for register write (Property 2)
    - **Property 2: Register write sends correct data**
    - Generate valid register addresses and byte values
    - Verify _write_register calls write_byte_data with correct arguments
    - **Validates: Requirements 1.3**

  - [x] 3.4 Write property test for I2C error context (Property 3)
    - **Property 3: I2C errors include diagnostic context**
    - Generate register addresses and device addresses
    - Mock SMBus to raise OSError
    - Verify re-raised OSError message contains register address, device address, and original error
    - **Validates: Requirements 1.4**

- [x] 4. Implement sensor class — initialization and resource management
  - [x] 4.1 Implement __init__ with validation, bus open, GPIO setup, and reset with retry
    - Validate I2C address using validators module
    - Open smbus2.SMBus with bus number parameter
    - Setup gpiozero.DigitalInputDevice for IRQ pin (BCM numbering, no pull resistor)
    - Implement `_reset_with_retry()` — up to 3 attempts, 1000ms total timeout
    - Implement phased error recovery: cleanup partially acquired resources on failure
    - Raise ConnectionError if sensor doesn't respond after retries
    - Raise OSError if I2C bus cannot be opened
    - Add WARNING logging before raising exceptions
    - _Requirements: 1.5, 2.1, 2.2, 2.5, 12.1, 12.2, 12.3, 12.4, 9.4_

  - [x] 4.2 Implement context manager (__enter__, __exit__) and close() method
    - `__enter__` returns self
    - `__exit__` calls close(), does not suppress exceptions (returns False)
    - `close()` releases GPIO and I2C resources, safe to call multiple times
    - Implement `_ensure_open()` check — raises RuntimeError if closed
    - Add _ensure_open() guard to all public methods except close() and __exit__
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 4.3 Write property test for close() idempotence (Property 7)
    - **Property 7: close() is idempotent**
    - Generate number of consecutive close() calls (1–10)
    - Verify no exception raised on any call after the first
    - **Validates: Requirements 3.4**

  - [x] 4.4 Write property test for post-close RuntimeError (Property 8)
    - **Property 8: Post-close methods raise RuntimeError**
    - Generate selections from public methods (excluding close/exit)
    - Call close() then call selected method
    - Verify RuntimeError is raised
    - **Validates: Requirements 3.5**

- [x] 5. Checkpoint - Ensure core infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement sensor class — configuration methods
  - [x] 6.1 Implement configuration setter and getter methods
    - `set_indoors()` / `set_outdoors()` — write AFE gain using named constants
    - `set_noise_floor_level(level)` / `get_noise_floor_level()` — validate, read-modify-write
    - `set_watchdog_threshold(threshold)` / `get_watchdog_threshold()` — validate, read-modify-write
    - `set_spike_rejection(rejection)` / `get_spike_rejection()` — validate, read-modify-write
    - `set_tuning_caps(capacitance)` — validate, shift right by 3, write to TUN_CAP bits
    - `set_min_strikes(strikes)` — validate, map to register encoding, write
    - `set_lco_fdiv(division)` — validate, shift left by 6, write to LCO_FDIV bits
    - `set_irq_output_source(source)` — write correct display bit (fix LCO bug: 0x80 not 0x40)
    - `enable_disturber()` / `disable_disturber()` — write MASK_DIST bit
    - Add INFO logging for each configuration change
    - Add type hints and Google-style docstrings to all methods
    - _Requirements: 4.6, 5.1, 5.2, 5.3, 5.4, 5.6, 5.7, 5.8, 6.1, 7.1, 7.3, 9.2_

  - [x] 6.2 Implement clear_statistics with correct 4-write sequence
    - Write CL_STAT bit in sequence: low(0x00), high(0x40), low(0x00), high(0x40)
    - Use named constants for register and mask
    - _Requirements: 6.2_

  - [x] 6.3 Implement power_up, power_down, and reset methods
    - `power_up()` — clear PWD bit, calibrate RCO, toggle DISP_SRCO
    - `power_down()` — set PWD bit
    - `reset()` — write CMD_PRESET_DEFAULT to REG_PRESET_DEFAULT, wait 2ms
    - _Requirements: 4.6_

  - [x] 6.4 Write property test for configuration logging (Property 9)
    - **Property 9: Configuration changes emit INFO log**
    - Generate valid configuration values for each setter
    - Verify exactly one INFO log record emitted containing the new value
    - **Validates: Requirements 9.2**

  - [x] 6.5 Write property test for I2C DEBUG logging (Property 10)
    - **Property 10: I2C operations emit DEBUG log**
    - Generate register operations (reads and writes)
    - Verify DEBUG log record emitted with register address and value
    - **Validates: Requirements 9.3**

- [x] 7. Implement sensor class — data reading and interrupt handling
  - [x] 7.1 Implement data reading methods
    - `get_interrupt_source()` — wait 3ms per datasheet, read INT bits, return code
    - `get_lightning_distance_km()` — read DISTANCE register, mask bits 5:0
    - `get_strike_energy_raw()` — combine 3 registers into 21-bit value (no division)
    - `get_strike_energy_normalized()` — divide raw by 2,097,151 for [0.0, 1.0] range
    - Add type hints and Google-style docstrings
    - _Requirements: 6.3, 6.4, 6.5, 7.1, 7.3_

  - [x] 7.2 Write property test for strike energy assembly (Property 6)
    - **Property 6: Strike energy assembly and normalization**
    - Generate three byte values (LSB: 0–255, MSB: 0–255, MMSB: 0–31)
    - Verify raw = (MMSB << 16) | (MSB << 8) | LSB
    - Verify normalized = raw / 2,097,151 in [0.0, 1.0]
    - **Validates: Requirements 6.3, 6.4**

  - [x] 7.3 Implement interrupt callback registration
    - `register_interrupt_callback(callback)` — set gpiozero `when_activated`
    - Replacing callback replaces previous one
    - If no callback registered, interrupt is silently ignored
    - Callback invoked within gpiozero's edge detection thread
    - Lock acquired before any I2C operations in callback context
    - _Requirements: 2.3, 2.4, 2.6, 11.2, 11.4_

- [x] 8. Checkpoint - Ensure sensor class tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Create example scripts
  - [x] 9.1 Create examples/lightning_detection.py
    - Demonstrate interrupt-based lightning detection with callback
    - Use context manager pattern
    - Read interrupt source, print distance and energy on lightning event
    - Use BCM pin numbering with physical-to-BCM mapping in comments
    - Import from `dfrobot_as3935` package (no sys.path manipulation)
    - Demonstrate error handling for initialization failure
    - _Requirements: 10.1, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 9.2 Create examples/sensor_configuration.py
    - Demonstrate setting noise floor, watchdog threshold, spike rejection
    - Demonstrate indoor/outdoor mode selection
    - Demonstrate antenna tuning capacitance configuration
    - Use context manager pattern
    - Use BCM pin numbering with comments
    - Import from `dfrobot_as3935` package
    - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 10. Create test infrastructure and unit tests
  - [x] 10.1 Create tests/conftest.py with shared fixtures
    - Create `mock_smbus` fixture patching `smbus2.SMBus`
    - Create `mock_gpio` fixture patching `gpiozero.DigitalInputDevice`
    - Create `sensor` fixture combining both mocks for a ready-to-use sensor instance
    - Configure mock_smbus.read_byte_data default return value
    - _Requirements: 13.1, 13.2_

  - [x] 10.2 Create tests/test_validators.py with unit tests
    - Test each validator with valid inputs (no exception)
    - Test each validator with invalid inputs (ValueError raised)
    - Verify error messages contain parameter name, value, and constraint
    - _Requirements: 13.3_

  - [x] 10.3 Create tests/test_sensor.py with unit tests
    - Test context manager __enter__ returns self
    - Test __exit__ does not suppress exceptions
    - Test clear_statistics writes exact 4-write sequence
    - Test set_irq_output_source(3) writes 0x80 to display bits
    - Test callback replacement behavior
    - Test initialization retry logic and timeout
    - Test resource cleanup on partial initialization failure
    - Test RLock reentrant acquisition (no deadlock)
    - Test each public method nominal path and error path
    - _Requirements: 13.2, 13.4, 13.5_

  - [x] 10.4 Create tests/test_constants.py with smoke tests
    - Verify all named constants are defined and importable
    - Verify constant values match datasheet (indoor=0x24, outdoor=0x1C, etc.)
    - Verify __all__ exports expected names
    - Verify no print() statements in library code
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.5 Create tests/test_properties.py with all property-based tests
    - Consolidate all Hypothesis property tests (Properties 1–10)
    - Add pytest markers for property tests
    - Ensure minimum 100 iterations per property
    - Tag each test with feature and property number in comments
    - _Requirements: 13.1_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Post-audit improvements
  - [x] 12.1 Add py.typed marker to pyproject.toml packaging
    - Added `[tool.setuptools.package-data]` section with `dfrobot_as3935 = ["py.typed"]`
    - Ensures PEP 561 type checker support when package is installed via pip
  - [x] 12.2 Add `configure()` convenience method to sensor class
    - Signature: `configure(*, capacitance=96, indoor=True, disturber=True)`
    - Calls set_indoors/set_outdoors, enable/disable_disturber, set_tuning_caps
    - Full type hints, docstring, validation, and INFO logging
  - [x] 12.3 Add tests for `configure()` method
    - 7 tests covering defaults, indoor=False, disturber=False, custom capacitance, invalid inputs, post-close error
    - All 302 tests pass

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All tests run without physical hardware using mocked I2C and GPIO
- The implementation uses Python 3.11+ with smbus2 and gpiozero as runtime dependencies
- Named constants from constants.py must be used throughout — no magic numbers in sensor.py

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "4.1"] },
    { "id": 4, "tasks": ["4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4", "6.1", "6.3"] },
    { "id": 6, "tasks": ["6.2", "6.4", "6.5", "7.1"] },
    { "id": 7, "tasks": ["7.2", "7.3"] },
    { "id": 8, "tasks": ["9.1", "9.2"] },
    { "id": 9, "tasks": ["10.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "10.4", "10.5"] }
  ]
}
```
