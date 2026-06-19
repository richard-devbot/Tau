"""Build a ``/settings`` sub-panel for an extension from a declarative manifest schema.

Extensions can describe their settings in ``manifest.json`` instead of writing
imperative ``register_settings`` code. The framework reads the schema, builds the
panel, reads current values from the extension's config, and wires an ``on_change``
that — only when a value actually changed — persists to settings.json and reloads
just that extension so the change applies live.

Manifest shape (under the app key, e.g. ``"tau"``)::

    "settings": {
      "title": "Web search",
      "fields": [
        {"key": "engine", "label": "Search engine", "type": "enum",
         "values": ["ddgs", "exa", "tavily"], "default": "ddgs"},

        {"key": "exa", "label": "Exa", "type": "group", "fields": [
          {"key": "api_key", "label": "API key", "type": "secret"},
          {"key": "results", "label": "Results", "type": "int",
           "default": 10, "min": 1, "max": 50}
        ]}
      ]
    }

Field ``type`` values:
  group           nested sub-panel; ``fields`` are rendered one level deeper and
                  their keys are prefixed with the group key (``exa.api_key``)
  enum / select   cycle through ``values`` (required, non-empty)
  bool            toggle off/on (stored in config as a JSON boolean)
  int             numeric text input; optional ``min`` / ``max`` clamp
  string / secret free text input; optional ``pattern`` (regex) the value must match

Keys support dot-notation directly too (``"exa.api_key"``). Unknown types and
malformed fields are skipped with a logged warning rather than rendering a
misleading control.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable

from tau.extensions.api import ExtensionSettingsRegistration
from tau.tui.components.settings_modal import SettingItem

_log = logging.getLogger(__name__)

_LEAF_TYPES = {"enum", "select", "bool", "int", "string", "secret", "text"}


def _get_nested(d: dict, path: str, default: Any = "") -> Any:
    obj: Any = d
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return default
        obj = obj[part]
    return obj if obj is not None else default


def _coerce(field_type: str, value: str, field: dict) -> Any:
    """Convert the panel's string value to the type the config should store."""
    if field_type == "bool":
        return str(value).lower() in ("on", "true")
    if field_type == "int":
        try:
            n = int(value)
        except (TypeError, ValueError):
            return field.get("default", 0)
        lo, hi = field.get("min"), field.get("max")
        if isinstance(lo, int):
            n = max(lo, n)
        if isinstance(hi, int):
            n = min(hi, n)
        return n
    return value


def _valid(field_type: str, value: str, field: dict) -> bool:
    """Reject an incoming value that violates the field's declared constraints."""
    if field_type == "int":
        try:
            int(value)
        except (TypeError, ValueError):
            return False
    if field_type in ("string", "secret", "text"):
        pattern = field.get("pattern")
        if pattern and not re.fullmatch(pattern, value or ""):
            return False
    return True


def build_manifest_panel(
    schema: dict,
    config: dict,
    *,
    default_title: str,
    apply: Callable[[str, Any], None],
) -> ExtensionSettingsRegistration | None:
    """Construct an :class:`ExtensionSettingsRegistration` from a manifest schema.

    ``apply(key, value)`` is called with the full dot-path key and the coerced
    value when — and only when — a field's value actually changes. Returns
    ``None`` if the schema yields no usable items.
    """
    field_defs: dict[str, dict] = {}   # full key -> field def (for coerce/validate)
    currents: dict[str, Any] = {}      # full key -> current config value (for diff)

    def build_items(fields: list, prefix: str) -> list[SettingItem]:
        items: list[SettingItem] = []
        for f in fields:
            if not isinstance(f, dict):
                _log.warning("settings_schema: skipping non-object field %r", f)
                continue
            key = f.get("key")
            if not key:
                _log.warning("settings_schema: skipping field with no 'key': %r", f)
                continue
            full = f"{prefix}.{key}" if prefix else key
            label = f.get("label", key)
            description = f.get("description", "")
            ftype = str(f.get("type") or "string").lower()

            # ── Nested group → sub-panel ──────────────────────────────────────
            if ftype == "group" or "fields" in f:
                children = build_items(f.get("fields") or [], full)
                if children:
                    items.append(SettingItem(
                        id=full, label=label, description=description,
                        current_value="→",
                        submenu_title=f.get("title") or label,
                        submenu_settings=children,
                    ))
                continue

            if ftype not in _LEAF_TYPES:
                _log.warning("settings_schema: unknown field type %r for %r — skipping", ftype, full)
                continue
            if ftype in ("enum", "select") and not f.get("values"):
                _log.warning("settings_schema: enum field %r has no values — skipping", full)
                continue

            current = _get_nested(config, full, f.get("default", ""))
            field_defs[full] = f

            if ftype in ("enum", "select"):
                currents[full] = current
                items.append(SettingItem(
                    id=full, label=label, description=description,
                    current_value=str(current),
                    values=[str(v) for v in f.get("values", [])],
                ))
            elif ftype == "bool":
                stored = current is True or str(current).lower() in ("true", "on")
                currents[full] = stored  # config-space bool, matches _coerce output
                items.append(SettingItem(
                    id=full, label=label, description=description,
                    current_value="on" if stored else "off",
                    values=["off", "on"],
                ))
            else:  # string, secret, int, text
                currents[full] = current
                items.append(SettingItem(
                    id=full, label=label, description=description,
                    current_value=str(current if current is not None else ""),
                    text_input=True,
                ))
        return items

    items = build_items(schema.get("fields") or [], "")
    if not items:
        return None

    # Surface the first top-level bool (e.g. a master "Enabled" switch) as an
    # on/off summary on the extension's parent row in the main /settings list.
    summary = ""
    summary_key = ""
    for f in schema.get("fields") or []:
        if isinstance(f, dict) and str(f.get("type") or "").lower() == "bool" and f.get("key"):
            summary_key = f["key"]
            summary = "on" if currents.get(summary_key) else "off"
            break

    def on_change(key: str, value: str) -> None:
        field = field_defs.get(key)
        if field is None:
            return  # not a leaf field we built (e.g. a group row) — ignore
        ftype = str(field.get("type") or "string").lower()
        if not _valid(ftype, value, field):
            _log.warning("settings_schema: invalid value %r for %r — ignored", value, key)
            return
        coerced = _coerce(ftype, value, field)
        if coerced == currents.get(key):
            return  # no change vs in-memory config — skip persist + reload
        currents[key] = coerced
        apply(key, coerced)

    return ExtensionSettingsRegistration(
        title=schema.get("title") or default_title,
        items=items,
        on_change=on_change,
        summary=summary,
        summary_key=summary_key,
    )
