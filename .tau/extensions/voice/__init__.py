"""Voice input extension — hold Space to record, release to transcribe."""

from __future__ import annotations

import asyncio
import io
import logging
import time
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tau.extensions.api import ExtensionAPI

_log = logging.getLogger(__name__)

# How long with no space event before we treat the key as released.
# Must exceed the OS key-repeat initial delay (typically 300–700 ms on macOS/Linux).
# On Kitty terminals (Tau default) the real release event fires immediately and
# cancels the watcher, so this only matters for non-Kitty terminals.
_RELEASE_GAP = 1.0


@dataclass
class _VoiceConfig:
    enabled: bool = True
    stt_model: str = "whisper-1"
    stt_provider: str = "openai"
    hold_seconds: float = 2.0
    sample_rate: int = 16000


class _VoiceController:
    """State machine for space-hold voice recording.

    Flow
    ────
    1. Initial space press  → consume key, start 2 s timer + release-gap watcher.
       Mode: waiting.  Mic is NOT open yet.
    2. Space auto-repeats   → update last-event timestamp, stay consumed.
    3. 2 s elapses          → open mic, switch to mode: recording, show animation.
    4. Key released         → detected via Kitty release event OR 250 ms repeat gap.
       • mode was waiting   → held < 2 s: type one space, go idle.
       • mode was recording → held ≥ 2 s: stop mic, transcribe.
    """

    _RECORDING_FRAMES = ["Recording .", "Recording ..", "Recording ..."]
    _TRANSCRIBING_FRAMES = ["Transcribing .", "Transcribing ..", "Transcribing ..."]

    def __init__(self, layout: Any, cfg: _VoiceConfig, settings: Any = None) -> None:
        self._layout = layout
        self._tui = layout._tui
        self._cfg = cfg
        self._settings = settings

        # Toggled by the /voice command. When disabled, space behaves normally.
        self._enabled = True

        # Modes: idle | waiting | recording | transcribing
        self._mode = "idle"
        self._press_time: float = 0.0
        self._last_space_time: float = 0.0
        # Observed auto-repeat interval (seconds). Measured from the gap between
        # consecutive space events so the release watcher can trip just above the
        # real cadence instead of a flat, conservative delay. 0.0 = not measured.
        self._repeat_interval: float = 0.0

        self._activation_task: asyncio.Task | None = None
        self._watcher_task: asyncio.Task | None = None
        self._animation_task: asyncio.Task | None = None

        self._audio_frames: list[Any] = []
        self._stream: Any = None
        self._original_placeholder: str = layout.input._placeholder

    # ── Enable/disable + model resolution ──────────────────────────────────────

    def toggle(self) -> bool:
        """Flip voice capture on/off. Returns the new enabled state."""
        self._enabled = not self._enabled
        if not self._enabled and self._mode in ("waiting", "recording"):
            # Tear down any in-flight capture so a held space is released cleanly.
            self._handle_release()
        return self._enabled

    def _resolve_stt(self) -> tuple[str, str]:
        """Resolve the STT (voice) model/provider: settings ``model.voice`` first,
        then the extension's configured defaults.
        """
        if self._settings is not None:
            ref = self._settings.get_model_ref("voice")
            if ref is not None and ref.id:
                return ref.id, (ref.provider or self._cfg.stt_provider)
        return self._cfg.stt_model, self._cfg.stt_provider

    # ── Placeholder ───────────────────────────────────────────────────────────

    def _set_placeholder(self, text: str) -> None:
        self._layout.input._placeholder = text
        self._tui.request_render()

    def _restore_placeholder(self) -> None:
        self._layout.input._placeholder = self._original_placeholder
        self._tui.request_render()

    # ── Animation ─────────────────────────────────────────────────────────────

    def _start_animation(self, frames: list[str]) -> None:
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
        self._animation_task = asyncio.ensure_future(self._animate(frames))

    def _stop_animation(self) -> None:
        if self._animation_task and not self._animation_task.done():
            self._animation_task.cancel()
        self._animation_task = None

    async def _animate(self, frames: list[str]) -> None:
        i = 0
        while True:
            self._set_placeholder(frames[i % len(frames)])
            i += 1
            await asyncio.sleep(0.4)

    # ── Background tasks ──────────────────────────────────────────────────────

    def _cancel_task(self, task: asyncio.Task | None) -> None:
        if task and not task.done():
            task.cancel()

    async def _activation_timer(self) -> None:
        """Open the mic and show Recording animation after hold_seconds."""
        await asyncio.sleep(self._cfg.hold_seconds)
        if self._mode != "waiting":
            return
        if not self._open_stream():
            self._mode = "idle"
            return
        self._mode = "recording"
        self._start_animation(self._RECORDING_FRAMES)

    def _release_gap(self) -> float:
        """Seconds of silence that mean the key was released.

        Once the auto-repeat cadence is known we trip just above it (≈2.5×,
        clamped to 0.25–_RELEASE_GAP) so release feels immediate. Before any
        repeat is measured — i.e. still inside the OS initial-repeat delay — we
        stay at the conservative _RELEASE_GAP to avoid a false release.
        """
        if self._repeat_interval <= 0.0:
            return _RELEASE_GAP
        return max(0.25, min(_RELEASE_GAP, self._repeat_interval * 2.5))

    async def _release_watcher(self) -> None:
        """Fallback release detector for terminals without Kitty key-up events.

        Polls every 50 ms. If no space event has arrived for the adaptive
        release gap the key has been released — trigger the same logic as a
        Kitty key-up.
        """
        while True:
            await asyncio.sleep(0.05)
            if self._mode not in ("waiting", "recording"):
                return
            if time.monotonic() - self._last_space_time >= self._release_gap():
                self._handle_release()
                return

    # ── Microphone ────────────────────────────────────────────────────────────

    def _open_stream(self) -> bool:
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError:
            _log.error("sounddevice not installed — voice extension cannot record")
            self._set_placeholder("Voice: sounddevice missing (check extension deps)")
            asyncio.ensure_future(self._clear_after(3.0))
            return False

        self._audio_frames = []

        def _cb(indata: Any, *_: Any) -> None:
            self._audio_frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self._cfg.sample_rate,
                channels=1,
                dtype="int16",
                callback=_cb,
            )
            self._stream.start()
        except Exception as exc:
            _log.error("failed to open mic: %s", exc)
            self._set_placeholder(f"Voice: mic error — {exc!s:.40}")
            asyncio.ensure_future(self._clear_after(3.0))
            return False

        return True

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ── Release logic (shared by Kitty and watcher) ───────────────────────────

    def _handle_release(self) -> None:
        if self._mode not in ("waiting", "recording"):
            return

        prior_mode = self._mode
        self._cancel_task(self._activation_task)
        self._cancel_task(self._watcher_task)
        self._activation_task = None
        self._watcher_task = None

        self._close_stream()
        self._stop_animation()

        if prior_mode == "waiting":
            # Short press — type the space we held back
            self._restore_placeholder()
            self._mode = "idle"
            self._layout.input.insert_at_cursor(" ")
            self._tui.request_render()
        else:
            # Long press — send captured audio to STT
            asyncio.ensure_future(self._transcribe())

    # ── Transcription ─────────────────────────────────────────────────────────

    async def _transcribe(self) -> None:
        self._mode = "transcribing"
        self._start_animation(self._TRANSCRIBING_FRAMES)

        try:
            import numpy as np

            if not self._audio_frames:
                self._stop_animation()
                self._restore_placeholder()
                self._mode = "idle"
                return

            audio_data = np.concatenate(self._audio_frames, axis=0)

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._cfg.sample_rate)
                wf.writeframes(audio_data.tobytes())
            wav_bytes = buf.getvalue()

            from tau.inference.api.audio.service import AudioLLM
            from tau.inference.types import AudioFormat, STTContext

            model_id, provider = self._resolve_stt()
            llm = AudioLLM(model_id, provider)
            result = await llm.transcribe(STTContext(audio=wav_bytes, format=AudioFormat.WAV))

            self._stop_animation()
            self._restore_placeholder()

            if result.text.strip():
                self._layout.input.insert_at_cursor(result.text.strip())
                self._tui.request_render()

            self._mode = "idle"

        except Exception as exc:
            _log.exception("voice transcription failed")
            self._stop_animation()
            msg = str(exc)
            suffix = "..." if len(msg) > 45 else ""
            self._set_placeholder(f"Transcription failed: {msg[:45]}{suffix}")
            self._mode = "idle"
            asyncio.ensure_future(self._clear_after(3.0))

    async def _clear_after(self, delay: float) -> None:
        await asyncio.sleep(delay)
        self._restore_placeholder()

    # ── Input intercept ───────────────────────────────────────────────────────

    def on_key(self, event: Any) -> bool | None:
        from tau.tui.input import KeyEvent

        if not self._enabled or not isinstance(event, KeyEvent):
            return None

        is_space = event.matches("space")

        # Non-space key while active: abort cleanly and restore the held space
        if not is_space:
            if self._mode in ("waiting", "recording"):
                self._cancel_task(self._activation_task)
                self._cancel_task(self._watcher_task)
                self._activation_task = None
                self._watcher_task = None
                self._close_stream()
                self._stop_animation()
                self._restore_placeholder()
                self._mode = "idle"
                self._layout.input.insert_at_cursor(" ")
                self._tui.request_render()
            return None

        # ── Space key ────────────────────────────────────────────────────────

        # Kitty key-release
        if event.released:
            self._handle_release()
            return True

        # Initial press (idle → waiting)
        if self._mode == "idle" and not event.repeat:
            self._press_time = time.monotonic()
            self._last_space_time = self._press_time
            # Forget the previous hold's cadence so the release watcher stays
            # conservative until this hold's repeats are measured — otherwise it
            # could false-trip during the OS initial-repeat delay.
            self._repeat_interval = 0.0
            self._mode = "waiting"
            self._activation_task = asyncio.ensure_future(self._activation_timer())
            self._watcher_task = asyncio.ensure_future(self._release_watcher())
            return True  # consume; space will be re-emitted if released early

        # Auto-repeat while waiting or recording — keep timestamp fresh and
        # learn the repeat cadence (used to size the release gap).
        if self._mode in ("waiting", "recording"):
            now = time.monotonic()
            gap = now - self._last_space_time
            # Ignore the long initial key-repeat delay and any outliers; only
            # steady-state intervals (< _RELEASE_GAP) describe the real cadence.
            if 0.0 < gap < _RELEASE_GAP:
                self._repeat_interval = gap
            self._last_space_time = now
            return True

        # Consume space during transcription too
        if self._mode == "transcribing":
            return True

        return None


def register(tau: ExtensionAPI) -> None:
    from tau.extensions.settings import ExtensionSettings

    cfg_raw = ExtensionSettings(_VoiceConfig, tau.config)
    cfg = _VoiceConfig(
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
        controller = _VoiceController(layout, cfg, ctx.settings)
        state["controller"] = controller
        layout._tui.on_input_intercept(controller.on_key)
