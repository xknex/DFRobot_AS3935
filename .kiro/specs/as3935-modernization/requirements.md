# Requirements Document

## Introduction

Modernize the DFRobot AS3935 Lightning Sensor Python library to run correctly on Raspberry Pi Zero 2W with Python 3.11+ and Raspberry Pi OS Bookworm. The modernization replaces deprecated dependencies (`smbus`, `RPi.GPIO`), introduces proper package structure, adds type safety, improves error handling, fixes hardware protocol bugs per the AS3935 datasheet, and establishes a testable codebase.

## Glossary

- **Library**: The DFRobot_AS3935 Python package that communicates with the AS3935 lightning sensor over I2C
- **Sensor**: The AS3935 lightning sensor IC accessed via I2C bus on the Raspberry Pi
- **I2C_Bus**: The I2C communication interface provided by `smbus2` for reading/writing sensor registers
- **GPIO_Interface**: The GPIO abstraction layer (using `gpiozero` or `rpi-lgpio`) for interrupt detection on the Raspberry Pi
- **Register**: An 8-bit hardware register on the AS3935 sensor, addressed 0x00–0x08
- **IRQ_Pin**: The interrupt request pin on the AS3935 that signals lightning events, disturbers, or noise
- **Interrupt_Source**: The type of event that triggered the IRQ pin (lightning, disturber, or noise)
- **Context_Manager**: A Python object implementing `__enter__` and `__exit__` for resource lifecycle management
- **Bookworm**: Raspberry Pi OS release (Debian 12) using kernel 6.6+ which removed the legacy sysfs GPIO interface

## Requirements

### Requirement 1: Replace smbus with smbus2

**User Story:** As a developer, I want the library to use `smbus2` instead of the legacy `smbus` C-extension, so that the library works reliably on modern Python without compiled dependencies.

#### Acceptance Criteria

1. THE Library SHALL instantiate `smbus2.SMBus` as the I2C communication backend and SHALL NOT import or use the legacy `smbus` module
2. WHEN reading a single register, THE I2C_Bus SHALL call `read_byte_data` (or `read_i2c_block_data` with a length of 1) on the specified register address and return a single integer value in the range 0–255
3. WHEN writing a register value, THE I2C_Bus SHALL call `write_byte_data` to write exactly 1 byte to the specified register address
4. IF an I2C communication error occurs (OSError raised by smbus2), THEN THE Library SHALL raise an `OSError` with a message indicating the register address, the device I2C address, and the underlying error cause
5. WHEN initializing the I2C_Bus, THE Library SHALL accept a bus number parameter (default: 1) and a device address parameter, and pass the bus number to `smbus2.SMBus`

### Requirement 2: Replace RPi.GPIO with modern GPIO library

**User Story:** As a developer, I want the library to use a GPIO library compatible with Raspberry Pi OS Bookworm (kernel 6.6+), so that interrupt detection works on modern systems where sysfs GPIO has been removed.

#### Acceptance Criteria

1. THE GPIO_Interface SHALL use `gpiozero` for interrupt pin detection
2. WHEN configuring the IRQ pin, THE GPIO_Interface SHALL configure the pin as an input using BCM pin numbering with no internal pull resistor enabled
3. WHEN a rising edge occurs on the IRQ_Pin, THE GPIO_Interface SHALL invoke the registered callback function within the same thread context that `gpiozero` uses for edge detection
4. THE Library SHALL provide a method to register a single user-defined callback for interrupt events, where registering a new callback replaces any previously registered callback
5. IF an invalid BCM pin number is provided during GPIO_Interface initialization, THEN THE Library SHALL raise a ValueError indicating the invalid pin number
6. IF a rising edge occurs on the IRQ_Pin and no callback has been registered, THEN THE GPIO_Interface SHALL ignore the interrupt without raising an error

### Requirement 3: Implement proper resource management

**User Story:** As a developer, I want the library to manage I2C bus and GPIO resources with context managers, so that resources are properly released when the sensor is no longer in use.

#### Acceptance Criteria

1. THE Library SHALL implement the Context_Manager protocol (`__enter__` and `__exit__`), where `__enter__` returns the Library instance
2. WHEN exiting the context, THE Library SHALL close the I2C_Bus connection and release the GPIO_Interface resources for the IRQ_Pin, attempting cleanup of both resources even if one cleanup operation raises an exception
3. WHEN `__exit__` is called with an exception, THE Library SHALL release all resources and propagate the exception (not suppress it)
4. IF the Library is used without a context manager, THEN THE Library SHALL provide an explicit `close()` method that performs the same resource cleanup as `__exit__` and is safe to call multiple times without raising an exception
5. IF any method is called after `close()` has been called, THEN THE Library SHALL raise a RuntimeError indicating that the resource has been closed

### Requirement 4: Define named constants for registers and bitmasks

**User Story:** As a developer, I want all magic numbers replaced with named constants, so that the code is readable and maintainable without constant reference to the AS3935 datasheet.

#### Acceptance Criteria

1. THE Library SHALL define named constants for all register addresses (0x00 through 0x08, 0x3C, 0x3D) as module-level variables importable from the package
2. THE Library SHALL define named constants for all bitmasks used in register read/write operations, with each constant name indicating the target register and field name (e.g., power-down bit, analog front-end gain, noise floor level, watchdog threshold, spike rejection, minimum lightning count, clear statistics, frequency division ratio, tuning capacitance, display output source, distance, energy LSB/MSB/MMSB)
3. THE Library SHALL define named constants for configuration values (indoor gain 0x24, outdoor gain 0x1C)
4. THE Library SHALL define named constants for interrupt source codes (lightning 0x08, disturber 0x04, noise 0x01)
5. THE Library SHALL define named constants for command bytes (PRESET_DEFAULT 0x96 written to register 0x3C, CALIB_RCO 0x96 written to register 0x3D)
6. WHEN library code performs a register read or write operation, THE Library SHALL reference the named constant instead of a numeric literal for the register address, bitmask, and configuration value

### Requirement 5: Add input validation

**User Story:** As a developer, I want the library to validate all parameters before writing to hardware registers, so that invalid configurations are caught early with clear error messages.

#### Acceptance Criteria

1. IF a capacitance value is provided that is not an integer, is not a multiple of 8, or is outside the range 0–120, THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the valid constraint (multiple of 8, range 0–120)
2. IF a noise floor level is provided that is not an integer or is outside the range 0–7, THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the valid range 0–7
3. IF a watchdog threshold is provided that is not an integer or is outside the range 0–15, THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the valid range 0–15
4. IF a spike rejection value is provided that is not an integer or is outside the range 0–15, THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the valid range 0–15
5. IF an I2C address is provided that is not one of the valid values (0x01, 0x02, 0x03), THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the set of valid addresses
6. IF an LCO frequency division ratio is provided that is not an integer or is outside the range 0–3, THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the valid range 0–3
7. IF a minimum strikes value is provided that is not one of the valid values (1, 5, 9, 16), THEN THE Library SHALL raise a ValueError with a message indicating the parameter name, the provided value, and the set of valid values
8. WHEN a setter method is called with a parameter, THE Library SHALL perform validation before any I2C write operation occurs

### Requirement 6: Fix hardware protocol bugs

**User Story:** As a developer, I want the library to correctly implement the AS3935 datasheet protocols, so that sensor communication is reliable and data readings are accurate.

#### Acceptance Criteria

1. WHEN the `set_irq_output_source` method is called with value 3 (LCO), THE Library SHALL write 0x80 to the display bits (register 0x08, bits 7:5) using a named constant identifying the LCO bit
2. WHEN the `clear_statistics` method is called, THE Library SHALL toggle the CL_STAT bit (register 0x02, bit 6) using exactly 4 writes in the sequence: set low (0x00), set high (0x40), set low (0x00), set high (0x40)
3. WHEN reading strike energy, THE Library SHALL combine registers 0x04, 0x05, and 0x06 (bits 4:0) into a 21-bit unsigned integer and return the raw value in the range 0 to 2097151 without any division or scaling
4. THE Library SHALL provide a separate method that returns the strike energy as a normalized float value calculated by dividing the raw 21-bit energy value by 2097151, producing a result in the range 0.0 to 1.0
5. WHEN the `read_data` method reads a register, THE I2C_Bus SHALL request exactly 1 byte from the specified register address

### Requirement 7: Add type hints and documentation

**User Story:** As a developer, I want the library to have complete type annotations and English docstrings, so that IDE tooling provides accurate autocompletion and the API is self-documenting.

#### Acceptance Criteria

1. THE Library SHALL provide type annotations for all public method parameters, return values, and the `__init__` constructor, such that running a static type checker in strict mode reports zero missing annotation errors for public interfaces
2. THE Library SHALL provide type annotations for all instance variables assigned in `__init__`, using either inline annotations or a class-level variable annotation
3. THE Library SHALL include English docstrings following Google style for all public methods, containing at minimum: a one-line summary, an `Args` section documenting each parameter, a `Returns` section documenting the return value, and a `Raises` section if the method raises exceptions
4. THE Library SHALL include a module-level docstring containing at minimum: a one-line summary of the library purpose, a description of the supported hardware (AS3935 lightning sensor), and a brief usage example demonstrating instantiation
5. THE Library SHALL define "public method" as any method whose name does not begin with an underscore character, plus the `__init__` method

### Requirement 8: Implement proper Python package structure

**User Story:** As a developer, I want the library installable via pip with a `pyproject.toml`, so that I can manage it as a proper dependency without `sys.path` hacks.

#### Acceptance Criteria

1. THE Library SHALL include a `pyproject.toml` file that specifies a build system backend, project name, version, description, license, and `requires-python = ">=3.11"`
2. THE Library SHALL include an `__init__.py` that exports the main sensor class and all public constants defined in Requirement 4 via `__all__`
3. THE Library SHALL declare `smbus2` and `gpiozero` as runtime dependencies with minimum version pins in `pyproject.toml`
4. WHEN installed via `pip install .` from the project root, THE Library SHALL be importable as `dfrobot_as3935` without path manipulation
5. IF `pip install .` is run on a Python version below 3.11, THEN pip SHALL refuse installation with an error indicating the Python version requirement

### Requirement 9: Add structured logging

**User Story:** As a developer, I want the library to use Python's logging module instead of print statements, so that I can control log verbosity and integrate with my application's logging configuration.

#### Acceptance Criteria

1. THE Library SHALL use the `logging` module with a logger named `dfrobot_as3935` and SHALL add only a `NullHandler` to that logger
2. WHEN a configuration change is made (indoor/outdoor mode, disturber enable/disable, noise floor level, watchdog threshold, spike rejection, LCO frequency division ratio), THE Library SHALL log the new value at INFO level
3. WHEN an I2C read or write operation is performed, THE Library SHALL log the register address and value at DEBUG level
4. IF an I2C communication error or input validation error occurs, THEN THE Library SHALL log the error details at WARNING level before raising the exception
5. THE Library SHALL not produce any output via `print()` statements
6. THE Library SHALL not configure any log handlers, formatters, or log level on the root logger or on its own logger

### Requirement 10: Provide modernized example scripts

**User Story:** As a developer, I want updated example scripts demonstrating the modernized API, so that I can quickly understand how to use the library on my Raspberry Pi Zero 2W.

#### Acceptance Criteria

1. THE Library SHALL include an example script demonstrating lightning detection that registers an interrupt callback on the IRQ_Pin, reads the Interrupt_Source, and prints the lightning distance and energy when lightning is detected
2. THE Library SHALL include an example script demonstrating sensor configuration that sets noise floor level, watchdog threshold, spike rejection, indoor/outdoor mode, and antenna tuning capacitance
3. WHEN demonstrating sensor usage, THE example scripts SHALL use the context manager pattern for resource management
4. THE example scripts SHALL use BCM pin numbering and document the physical-to-BCM pin mapping in comments
5. THE example scripts SHALL import the library using the package name `dfrobot_as3935` without `sys.path` manipulation
6. THE example scripts SHALL use `gpiozero` for GPIO access and `smbus2` for I2C communication, with no references to `RPi.GPIO` or `smbus`
7. IF sensor initialization fails in an example script, THEN THE example script SHALL demonstrate error handling by catching the exception and printing a message indicating the failure reason

### Requirement 11: Ensure thread safety for interrupt callbacks

**User Story:** As a developer, I want the library to safely handle concurrent access from interrupt callbacks and the main thread, so that register reads during interrupt handling do not corrupt state.

#### Acceptance Criteria

1. THE Library SHALL use a `threading.RLock` (reentrant lock) to serialize all I2C_Bus access, including single-register read-modify-write operations and multi-register read sequences that must complete atomically
2. WHEN an interrupt callback accesses sensor registers (read or write), THE Library SHALL acquire the lock before the first I2C_Bus operation and release it only after the last I2C_Bus operation in that method call completes
3. THE Library SHALL use local variables for intermediate register data within methods and SHALL NOT store temporary register values in mutable instance attributes between I2C_Bus operations
4. IF the lock is already held by the same thread, THEN THE Library SHALL allow reentrant acquisition without deadlocking

### Requirement 12: Proper error handling on initialization

**User Story:** As a developer, I want the library to raise clear exceptions on initialization failure, so that my application can handle errors gracefully instead of hanging in an infinite loop.

#### Acceptance Criteria

1. IF the sensor does not respond to the reset command within 1000 milliseconds after up to 3 retry attempts, THEN THE Library SHALL raise a `ConnectionError` with a message indicating the I2C address and bus number
2. IF the I2C bus cannot be opened, THEN THE Library SHALL raise an `OSError` with a message indicating the bus identifier that failed to open and the underlying OS error reason
3. THE Library SHALL not use infinite loops (`while True: pass`) for error handling
4. IF any exception is raised during initialization, THEN THE Library SHALL release any partially acquired resources before propagating the exception to the caller

### Requirement 13: Add unit test infrastructure

**User Story:** As a developer, I want a test suite with mocked I2C communication, so that I can verify library logic without physical hardware.

#### Acceptance Criteria

1. THE Library SHALL include a test suite using `pytest` as the test framework, and SHALL declare `pytest` as a test dependency in `pyproject.toml`
2. THE Library SHALL include tests that use `unittest.mock` to patch the `smbus2.SMBus` interface, verifying that register read operations call `read_byte_data` and write operations call `write_byte_data` with the correct register address and value
3. THE Library SHALL include tests that verify each input validation rule from Requirement 5 raises a `ValueError` when provided with an out-of-range or invalid parameter
4. WHEN a value is written to a register and then read back, THE Library SHALL produce the same value after applying the corresponding bitmask, for all registers 0x00 through 0x08 and all values within each register field's valid range
5. THE Library SHALL include at least one test for each public method of the sensor class, covering both the nominal path and at least one error path
