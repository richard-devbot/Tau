from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from tau.agent.types import AgentConfig, AgentContext, AgentPhase, PromptOptions, ContextUsage
from tau.hooks.service import Hooks
from tau.hooks.engine import MessageEndEvent, MessageRollbackEvent, SavePointEvent, SettledEvent
from tau.message.types import AgentMessage, AssistantMessage, TerminalExecutionMessage, LLMMessage, UserMessage, TextContent, ToolMessage
from tau.message.utils import strip_unusable_trailing_assistant
from tau.tool.types import ToolInvocation, ToolResult

if TYPE_CHECKING:
    from tau.engine.service import Engine
    from tau.session.manager import SessionManager
    from tau.runtime.service import Runtime
    from tau.session.compaction import CompactionPreparation



def _to_llm_messages(messages: list[AgentMessage]) -> list[LLMMessage]:
    """Convert AgentMessages to LLM-compatible messages.

    TerminalExecutionMessage   → UserMessage (Ran `cmd`\n```output```)
    CompactionSummaryMessage → UserMessage with summary wrapped in XML tags
    CustomMessage and other non-LLM types → skipped
    Empty AssistantMessages are visual-only markers (aborts, persisted API/credit
    errors) and are skipped — an assistant turn with neither content nor tool
    calls is invalid to send back and triggers provider 400s.
    """
    from tau.message.types import CompactionSummaryMessage, ToolCallContent, ThinkingContent
    result: list[LLMMessage] = []
    for msg in messages:
        if isinstance(msg, CompactionSummaryMessage):
            text = f"<context-summary>\n{msg.summary}\n</context-summary>"
            result.append(UserMessage.from_text(text))
        elif isinstance(msg, TerminalExecutionMessage):
            if not msg.exclude:
                result.append(msg.to_user_message())
        elif isinstance(msg, AssistantMessage):
            has_usable = any(
                isinstance(c, (TextContent, ToolCallContent, ThinkingContent))
                for c in msg.contents
            )
            if has_usable:
                result.append(msg)
        elif isinstance(msg, (UserMessage, ToolMessage)):
            result.append(msg)
    return result


class Agent:
    """
    High-level agent session tying together Engine and SessionManager.

    Call `invoke()` to run a user turn. The session persists each message
    and tracks token usage.
    """

    def __init__(
        self,
        engine: Engine,
        session_manager: SessionManager,
        config: AgentConfig,
        hooks: Hooks | None = None,
    ) -> None:
        self._engine = engine
        self._session_manager = session_manager
        self._config = config
        self._system_prompt: str = config.system_prompt
        self._context_tokens: int = 0
        self._context_window: int = config.context_window
        self._runtime: Runtime | None = None
        self.hooks = hooks or Hooks()

        self._phase: AgentPhase = AgentPhase.IDLE
        self._signal: asyncio.Event = asyncio.Event()
        self._compaction_failures: int = 0
        self._engine.options.before_tool_call = self._before_tool_call
        self._engine.options.after_tool_call = self._after_tool_call

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    @property
    def cwd(self) -> Path:
        """Get the current working directory."""
        return self._config.cwd

    @property
    def session_manager(self) -> SessionManager:
        """Get the session manager instance."""
        return self._session_manager

    def is_idle(self) -> bool:
        """Check if the agent is idle (not processing)."""
        return self._engine.is_idle

    def has_pending_messages(self) -> bool:
        """Check if there are pending messages in the queue."""
        return self._engine.has_pending_messages()

    def abort(self) -> None:
        """Request abort of current operation."""
        self._signal.set()

    def shutdown(self) -> None:
        """Shutdown the agent."""
        self._signal.set()

    def update_context_tokens(self) -> None:
        """Recalculate context token usage."""
        from tau.session.compaction import estimate_context_tokens
        session_ctx = self._session_manager.build_session_context()
        llm_messages = _to_llm_messages(session_ctx.messages)
        usage = estimate_context_tokens(llm_messages)
        self._context_tokens = usage.tokens

    def get_context_usage(self) -> ContextUsage | None:
        """Get current context token usage and limits."""
        self.update_context_tokens()
        percent = (self._context_tokens / self._context_window * 100) if self._context_window else None
        return ContextUsage(
            tokens=self._context_tokens,
            context_window=self._context_window,
            percent=percent,
        )

    def get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return self._system_prompt

    async def wait_for_idle(self) -> None:
        """Wait until the agent becomes idle."""
        await self._engine.wait_for_idle()

    async def new_session(self) -> None:
        """Create a new session."""
        if self._runtime is not None:
            await self._runtime.new_session()

    async def fork(self, entry_id: str) -> None:
        """Fork a session from a specific entry."""
        if self._runtime is not None:
            await self._runtime.fork_session(entry_id)

    async def switch_session(self, session_file: Path) -> None:
        """Switch to a different session."""
        if self._runtime is not None:
            await self._runtime.resume_session(session_file)

    # -------------------------------------------------------------------------
    # Engine-level tool hooks (pass-through)
    # -------------------------------------------------------------------------

    async def _before_tool_call(
        self,
        invocation: ToolInvocation,
        signal: asyncio.Event | None,
    ) -> ToolInvocation | None:
        return invocation

    async def _after_tool_call(
        self,
        invocation: ToolInvocation,
        result: ToolResult,
        signal: asyncio.Event | None,
    ) -> ToolResult | None:
        return result

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _on_message_end(self, event: MessageEndEvent) -> None:
        """Persist an incoming message to the session and track token usage."""
        message = event.message
        if message is None:
            return
        match message:
            case AssistantMessage():
                total = message.usage.input_tokens + message.usage.output_tokens
                if total:
                    self._context_tokens = total
                self._session_manager.append_message(message)
            case ToolMessage():
                self._session_manager.append_message(message)
            case _:
                pass

    async def _on_message_rollback(self, event: "MessageRollbackEvent") -> None:
        """Retract the last ``event.count`` persisted messages from the session.

        Fired when an interrupted tool turn is dropped: the assistant tool-call
        message and its tool-result message were already written, so remove them
        to keep the session consistent with what the engine replays.
        """
        for _ in range(event.count):
            if not self._session_manager.remove_last_message():
                break

    # -------------------------------------------------------------------------
    # Compaction
    # -------------------------------------------------------------------------

    async def compact(self, custom_instructions: str | None = None) -> bool:
        """Manually trigger context compaction. Returns True if compaction ran."""
        from tau.session.compaction import prepare_compaction
        from tau.hooks.engine import CompactionEndEvent
        entries = self._session_manager.get_branch()
        preparation = prepare_compaction(entries, self._config.compaction)
        if preparation is None:
            return False
        result, from_extension = await self._run_compaction(preparation, entries, manual=True, custom_instructions=custom_instructions)
        self._session_manager.append_compaction(
            summary=result.summary,
            first_kept_entry_id=result.first_kept_entry_id,
            tokens_before=result.tokens_before,
        )
        self._compaction_failures = 0
        await self.hooks.emit(CompactionEndEvent(
            manual=True,
            tokens_before=result.tokens_before,
            summary_length=len(result.summary),
            from_extension=from_extension,
        ))
        return True

    async def _check_compaction(self) -> None:
        """Auto-compact if context usage exceeds the threshold. Circuit-breaks after 3 failures."""
        from tau.session.compaction import (
            estimate_context_tokens, should_compact,
            prepare_compaction,
        )
        from tau.hooks.engine import CompactionEndEvent

        if self._compaction_failures >= 3:
            return

        settings = self._config.compaction
        if not settings.enabled:
            return

        entries = self._session_manager.get_branch()
        session_ctx = self._session_manager.build_session_context()
        llm_messages = _to_llm_messages(session_ctx.messages)

        usage = estimate_context_tokens(llm_messages)
        if not should_compact(usage.tokens, self._context_window, settings):
            return

        preparation = prepare_compaction(entries, settings)
        if preparation is None:
            return

        try:
            result, from_extension = await self._run_compaction(preparation, entries, manual=False)
            self._session_manager.append_compaction(
                summary=result.summary,
                first_kept_entry_id=result.first_kept_entry_id,
                tokens_before=result.tokens_before,
            )
            self._compaction_failures = 0
            await self.hooks.emit(CompactionEndEvent(
                manual=False,
                tokens_before=result.tokens_before,
                summary_length=len(result.summary),
                from_extension=from_extension,
            ))
        except Exception:
            self._compaction_failures += 1

    async def _run_compaction(self, preparation: "CompactionPreparation", entries: list, manual: bool, custom_instructions: str | None = None) -> tuple:
        """Emit before_compaction (allowing interception), then run the default algorithm.

        Returns (CompactionResult, from_extension: bool).
        Extensions may cancel (raises RuntimeError) or supply a custom CompactionResult.
        Exceptions in before_compaction handlers are swallowed — first non-error result wins,
        consistent with error-fallthrough behaviour.
        """
        from tau.session.compaction import compact as _compact
        from tau.hooks.types import BeforeCompactionEvent, BeforeCompactionResult, CompactionStartEvent

        before_results = await self.hooks.emit(BeforeCompactionEvent(
            preparation=preparation,
            entries=entries,
            manual=manual,
        ))

        for res in before_results:
            if not isinstance(res, BeforeCompactionResult):
                continue
            if res.cancel:
                raise RuntimeError("Compaction cancelled by extension")
            if res.compaction is not None:
                return res.compaction, True

        await self.hooks.emit(CompactionStartEvent(manual=manual))
        result = await _compact(preparation, self._engine.llm, custom_instructions=custom_instructions)  # type: ignore[arg-type]
        return result, False

    # -------------------------------------------------------------------------
    # Core turn entry point
    # -------------------------------------------------------------------------

    async def invoke(self, text: str, options: PromptOptions | None = None) -> None:
        """Run one user turn."""
        if self._phase != AgentPhase.IDLE:
            raise RuntimeError(f"Agent is busy (phase={self._phase!r}). Wait for the current operation to finish.")

        opts = options or PromptOptions()

        session_ctx = self._session_manager.build_session_context()
        llm_messages = _to_llm_messages(session_ctx.messages)
        llm_messages = strip_unusable_trailing_assistant(llm_messages, self._session_manager)

        if opts.images:
            user_message = UserMessage.with_images(text, list(opts.images))
        elif opts.audio:
            user_message = UserMessage.with_audio(text, list(opts.audio))
        elif opts.video:
            user_message = UserMessage.with_video(text, list(opts.video))
        else:
            user_message = UserMessage.from_text(text)
        self._session_manager.append_message(user_message, meta=opts.meta)
        llm_messages.append(user_message)

        ctx = AgentContext(
            system_prompt=self._system_prompt,
            messages=llm_messages,
            tools=self._engine.tools,
        )

        self._signal = asyncio.Event()
        self._engine.llm.api.options.signal = self._signal

        self._phase = AgentPhase.TURN
        try:
            await self._run(ctx)
        finally:
            self._phase = AgentPhase.IDLE

        await self.hooks.emit(SavePointEvent())

        await self._check_compaction()

        if not self._engine.has_pending_messages():
            await self.hooks.emit(SettledEvent())

    async def _run(self, ctx: AgentContext) -> None:
        unsubscribe = self.hooks.register(
            'message_end',
            lambda event: self._on_message_end(event),
        )
        unsubscribe_rollback = self.hooks.register(
            'message_rollback',
            lambda event: self._on_message_rollback(event),
        )
        try:
            await self._engine.run(ctx, signal=self._signal)
        finally:
            unsubscribe()
            unsubscribe_rollback()

        error = self._engine.state.error_message
        if error is not None:
            raise RuntimeError(f"Agent failed: {error}.")
