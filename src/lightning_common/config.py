"""Configuration module for Lightning Data Pipeline services.

Uses pydantic-settings with environment variable priority and TOML fallback.
Environment variables use the LIGHTNING_ prefix.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource


class CollectorSettings(BaseSettings):
    """Configuration for the Lightning Collector Service."""

    model_config = SettingsConfigDict(
        env_prefix="LIGHTNING_",
        toml_file="lightning.toml",
    )

    db_host: str
    db_port: int = Field(description="Database port (1-65535)")
    db_user: str
    db_password: str = Field(repr=False)
    db_name: str
    csv_file_path: str = "/var/lib/lightning/events.csv"
    sensor_i2c_address: int = Field(
        default=0x03, description="I2C address: 0x01, 0x02, or 0x03"
    )
    sensor_i2c_bus: int = 1
    sensor_irq_pin: int = 4
    buffer_max_size: int = 10000

    VALID_I2C_ADDRESSES: ClassVar[set[int]] = {0x01, 0x02, 0x03}

    @field_validator("db_port")
    @classmethod
    def validate_db_port(cls, v: int) -> int:
        """Validate that db_port is in the range 1-65535."""
        if not (1 <= v <= 65535):
            raise ValueError("db_port must be between 1 and 65535")
        return v

    @field_validator("sensor_i2c_address")
    @classmethod
    def validate_i2c_address(cls, v: int) -> int:
        """Validate that sensor_i2c_address is one of 0x01, 0x02, 0x03."""
        if v not in cls.VALID_I2C_ADDRESSES:
            raise ValueError(
                f"sensor_i2c_address must be one of 0x01, 0x02, 0x03, got {v:#04x}"
            )
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: object,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        """Customise settings sources: env vars take priority over TOML file."""
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )


class ApiSettings(BaseSettings):
    """Configuration for the Lightning REST API Service."""

    model_config = SettingsConfigDict(
        env_prefix="LIGHTNING_",
        toml_file="lightning.toml",
    )

    db_host: str
    db_port: int = Field(description="Database port (1-65535)")
    db_user: str
    db_password: str = Field(repr=False)
    db_name: str
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, description="API port (1-65535)")
    cors_origins: list[str] = ["*"]
    db_pool_size: int = 5

    @field_validator("db_port", "api_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate that port is in the range 1-65535."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: object,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        """Customise settings sources: env vars take priority over TOML file."""
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )
