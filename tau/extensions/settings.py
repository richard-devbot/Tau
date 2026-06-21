"""Extension settings utilities for schema validation and typed access."""

from __future__ import annotations

import dataclasses as dc
from dataclasses import fields
from typing import Any, TypeVar

T = TypeVar("T")


class ExtensionSettingsError(Exception):
    """Raised when extension settings validation fails."""

    pass


class ExtensionSettings[T]:
    """
    Typed wrapper for extension-specific settings.

    Allows extensions to define a dataclass schema and safely deserialize
    their configuration from settings.json with validation and defaults.

    Example:
        @dataclass
        class MyExtConfig:
            api_key: Optional[str] = None
            timeout_ms: int = 5000
            retry: Optional[RetryConfig] = None

        @dataclass
        class RetryConfig:
            enabled: bool = True
            max_attempts: int = 3

        def register(tau):
            config = ExtensionSettings(MyExtConfig, tau.config)
            api_key = config.get("api_key")
            retry_enabled = config.get_nested("retry.enabled", True)
    """

    def __init__(self, schema: type[T], raw_config: dict[str, Any] | None = None):
        """
        Initialize with a dataclass schema and raw configuration dict.

        Args:
            schema: A dataclass type defining the expected structure
            raw_config: Raw dict from tau.config (defaults to empty dict)

        Raises:
            ExtensionSettingsError: If schema is not a dataclass
        """
        if not dc.is_dataclass(schema):
            raise ExtensionSettingsError(f"Schema must be a dataclass, got {schema}")

        self._schema = schema
        self._raw = raw_config or {}
        self._instance = self._deserialize()

    def _deserialize(self) -> T:
        """Deserialize raw config dict into typed dataclass instance."""
        kwargs = {}

        for field in fields(self._schema):
            value = self._raw.get(field.name)

            # If value is missing, use field default
            if value is None:
                if field.default is not dc.MISSING:
                    value = field.default
                elif field.default_factory is not dc.MISSING:
                    value = field.default_factory()
                else:
                    value = None
            else:
                # If field expects a nested dataclass, recursively deserialize
                if dc.is_dataclass(field.type) and isinstance(value, dict):
                    nested_settings = ExtensionSettings(field.type, value)  # type: ignore[arg-type]
                    value = nested_settings._instance

            kwargs[field.name] = value

        return self._schema(**kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level setting value."""
        return getattr(self._instance, key, default)

    def get_nested(self, path: str, default: Any = None) -> Any:
        """
        Get a nested setting value using dot notation.

        Args:
            path: Dot-separated path like "retry.enabled" or "limits.timeout_ms"
            default: Value to return if path not found

        Returns:
            The value at the path, or default if not found
        """
        parts = path.split(".")
        obj = self._instance

        for part in parts:
            if obj is None:
                return default
            try:
                obj = getattr(obj, part)
            except AttributeError:
                return default

        return obj if obj is not None else default

    def to_dict(self) -> dict[str, Any]:
        """Convert the typed instance back to a dict (useful for serialization)."""
        return self._to_dict_recursive(self._instance)

    @staticmethod
    def _to_dict_recursive(obj: Any) -> Any:
        """Recursively convert dataclass instances to dicts."""
        if dc.is_dataclass(obj) and not isinstance(obj, type):
            result = {}
            for field in fields(obj):
                value = getattr(obj, field.name)
                result[field.name] = ExtensionSettings._to_dict_recursive(value)
            return result
        elif isinstance(obj, (list, tuple)):
            return [ExtensionSettings._to_dict_recursive(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: ExtensionSettings._to_dict_recursive(v) for k, v in obj.items()}
        return obj

    def __repr__(self) -> str:
        return f"ExtensionSettings({self._instance})"
