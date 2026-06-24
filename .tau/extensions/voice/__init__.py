"""Voice input extension — hold Space to record, release to transcribe.

Package layout
──────────────
- ``config.py``     — :class:`VoiceConfig` + the ``RELEASE_GAP`` constant.
- ``audio.py``      — stateless helpers: WAV encoding and the STT call.
- ``controller.py`` — :class:`VoiceController`, the space-hold state machine.
- ``__init__.py``   — this file: the ``register(tau)`` entry point that wires
  the ``/voice`` command and installs the key interceptor on ``tui_ready``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import VoiceConfig
from .controller import VoiceController

if TYPE_CHECKING:
    from tau.extensions.api import ExtensionAPI


def register(tau: ExtensionAPI) -> None:
    from tau.extensions.settings import ExtensionSettings

    cfg_raw = ExtensionSettings(VoiceConfig, tau.config)
    cfg = VoiceConfig(
        enabled=cfg_raw.get("enabled", True),
        stt_model=cfg_raw.get("stt_model", "whisper-1"),
        stt_provider=cfg_raw.get("stt_provider", "openai"),
        hold_seconds=float(cfg_raw.get("hold_seconds", 2.0)),
        sample_rate=int(cfg_raw.get("sample_rate", 16000)),
    )

    if not cfg.enabled:
        return

    # Populated in tui_ready so the /voice command can reach the live controller.
    state: dict[str, Any] = {"controller": None}

    def _toggle_voice(ctx: Any, _args: list[str]) -> None:
        controller = state["controller"]
        ui = ctx.ui if ctx.has_ui else None
        if controller is None:
            if ui is not None:
                ui.notify("Voice input is not ready yet.")
            return
        enabled = controller.toggle()
        if ui is not None:
            ui.notify(f"Voice input {'enabled' if enabled else 'disabled'}.")

    tau.register_command("voice", "Toggle voice input (hold Space) on/off", _toggle_voice)

    @tau.on("tui_ready")
    def _on_ready(_event: Any, ctx: Any) -> None:
        if not ctx.has_ui:
            return
        layout = getattr(ctx, "_layout", None)
        if layout is None:
            return
        controller = VoiceController(layout, cfg, ctx.settings)
        state["controller"] = controller
        layout._tui.on_input_intercept(controller.on_key)
