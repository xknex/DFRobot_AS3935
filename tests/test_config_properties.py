# Feature: lightning-data-pipeline, Property 5: Configuration environment variable priority
"""Property-based tests for configuration environment variable priority.

Tests that environment variables (with LIGHTNING_ prefix) always override
values specified in the TOML configuration file.

**Validates: Requirements 4.1**
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from lightning_common.config import CollectorSettings, ApiSettings


# ===========================================================================
# Strategies
# ===========================================================================

# Generate non-empty ASCII alphanumeric strings suitable for string config fields
# Restricted to ASCII to avoid Windows encoding issues when writing TOML files
_config_string_values = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="-_.",
        max_codepoint=127,
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")


# ===========================================================================
# Property 5: Configuration environment variable priority
# ===========================================================================


@pytest.mark.property
class TestProperty5EnvVarPriority:
    """Property 5: Configuration environment variable priority.

    For any configuration key that is set in both an environment variable and
    the TOML file with different values, the loaded configuration SHALL use
    the environment variable value.

    **Validates: Requirements 4.1**
    """

    @given(
        env_value=_config_string_values,
        toml_value=_config_string_values,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_env_var_overrides_toml_for_db_host(
        self, env_value: str, toml_value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env var LIGHTNING_DB_HOST overrides db_host in TOML file."""
        assume(env_value != toml_value)

        # Create a TOML file with the toml_value for db_host and all required fields
        toml_content = f"""
db_host = "{toml_value}"
db_port = 3306
db_user = "testuser"
db_password = "testpass"
db_name = "testdb"
csv_file_path = "/tmp/test.csv"
sensor_i2c_address = 3
sensor_i2c_bus = 1
sensor_irq_pin = 4
buffer_max_size = 10000
"""
        toml_file = tmp_path / "lightning.toml"
        toml_file.write_text(toml_content, encoding="utf-8")

        # Set the env var to override
        monkeypatch.setenv("LIGHTNING_DB_HOST", env_value)
        monkeypatch.setenv("LIGHTNING_DB_PORT", "3306")
        monkeypatch.setenv("LIGHTNING_DB_USER", "testuser")
        monkeypatch.setenv("LIGHTNING_DB_PASSWORD", "testpass")
        monkeypatch.setenv("LIGHTNING_DB_NAME", "testdb")

        # Monkeypatch the class-level model_config to point to our temp TOML file
        monkeypatch.setattr(
            CollectorSettings, "model_config",
            {**CollectorSettings.model_config, "toml_file": str(toml_file)},
        )

        # Load settings - env vars should take priority over TOML
        config = CollectorSettings()

        # The env var value should win over the TOML value
        assert config.db_host == env_value

    @given(
        env_value=_config_string_values,
        toml_value=_config_string_values,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_env_var_overrides_toml_for_db_user(
        self, env_value: str, toml_value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env var LIGHTNING_DB_USER overrides db_user in TOML file."""
        assume(env_value != toml_value)

        toml_content = f"""
db_host = "localhost"
db_port = 3306
db_user = "{toml_value}"
db_password = "testpass"
db_name = "testdb"
csv_file_path = "/tmp/test.csv"
sensor_i2c_address = 3
sensor_i2c_bus = 1
sensor_irq_pin = 4
buffer_max_size = 10000
"""
        toml_file = tmp_path / "lightning.toml"
        toml_file.write_text(toml_content, encoding="utf-8")

        monkeypatch.setenv("LIGHTNING_DB_HOST", "localhost")
        monkeypatch.setenv("LIGHTNING_DB_PORT", "3306")
        monkeypatch.setenv("LIGHTNING_DB_USER", env_value)
        monkeypatch.setenv("LIGHTNING_DB_PASSWORD", "testpass")
        monkeypatch.setenv("LIGHTNING_DB_NAME", "testdb")

        monkeypatch.setattr(
            CollectorSettings, "model_config",
            {**CollectorSettings.model_config, "toml_file": str(toml_file)},
        )

        config = CollectorSettings()

        assert config.db_user == env_value

    @given(
        env_value=_config_string_values,
        toml_value=_config_string_values,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_env_var_overrides_toml_for_db_name(
        self, env_value: str, toml_value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env var LIGHTNING_DB_NAME overrides db_name in TOML file."""
        assume(env_value != toml_value)

        toml_content = f"""
db_host = "localhost"
db_port = 3306
db_user = "testuser"
db_password = "testpass"
db_name = "{toml_value}"
csv_file_path = "/tmp/test.csv"
sensor_i2c_address = 3
sensor_i2c_bus = 1
sensor_irq_pin = 4
buffer_max_size = 10000
"""
        toml_file = tmp_path / "lightning.toml"
        toml_file.write_text(toml_content, encoding="utf-8")

        monkeypatch.setenv("LIGHTNING_DB_HOST", "localhost")
        monkeypatch.setenv("LIGHTNING_DB_PORT", "3306")
        monkeypatch.setenv("LIGHTNING_DB_USER", "testuser")
        monkeypatch.setenv("LIGHTNING_DB_PASSWORD", "testpass")
        monkeypatch.setenv("LIGHTNING_DB_NAME", env_value)

        monkeypatch.setattr(
            CollectorSettings, "model_config",
            {**CollectorSettings.model_config, "toml_file": str(toml_file)},
        )

        config = CollectorSettings()

        assert config.db_name == env_value

    @given(
        env_value=_config_string_values,
        toml_value=_config_string_values,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_env_var_overrides_toml_for_api_settings_db_host(
        self, env_value: str, toml_value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env var LIGHTNING_DB_HOST overrides db_host in TOML for ApiSettings."""
        assume(env_value != toml_value)

        toml_content = f"""
db_host = "{toml_value}"
db_port = 3306
db_user = "testuser"
db_password = "testpass"
db_name = "testdb"
api_host = "0.0.0.0"
api_port = 8000
db_pool_size = 5
"""
        toml_file = tmp_path / "lightning.toml"
        toml_file.write_text(toml_content, encoding="utf-8")

        monkeypatch.setenv("LIGHTNING_DB_HOST", env_value)
        monkeypatch.setenv("LIGHTNING_DB_PORT", "3306")
        monkeypatch.setenv("LIGHTNING_DB_USER", "testuser")
        monkeypatch.setenv("LIGHTNING_DB_PASSWORD", "testpass")
        monkeypatch.setenv("LIGHTNING_DB_NAME", "testdb")

        monkeypatch.setattr(
            ApiSettings, "model_config",
            {**ApiSettings.model_config, "toml_file": str(toml_file)},
        )

        config = ApiSettings()

        assert config.db_host == env_value
