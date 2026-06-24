from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import click

from tau.console.commands.auth import auth
from tau.console.commands.packages import install, list_packages, remove
from tau.console.commands.update import update
from tau.runtime.service import Runtime
from tau.settings.paths import get_app_version

_MODES = ("interactive", "print", "json", "rpc")
_OUTPUT_FORMATS = ("text", "json")


def resolve_mode(mode: str | None, print_flag: bool, prompt: str | None, output_format: str) -> str:
    """Determine the run mode: interactive, print, json, or rpc."""
    if mode is not None:
        return mode
    if prompt is not None:
        return "json" if output_format == "json" else "print"
    if print_flag or not sys.stdout.isatty():
        return "print"
    return "interactive"


def resolve_model(model: str | None, provider: str | None) -> tuple[str | None, str | None]:
    """Parse provider/model shorthand. Explicit --provider always wins."""
    if model and provider is None and "/" in model:
        inferred_provider, _, model_id = model.partition("/")
        return inferred_provider, model_id
    return provider, model  # None when not specified; runtime falls back to settings then default


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--version", "-v", is_flag=True, default=False, help="Print version and exit.")
@click.option("--debug", "-d", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--cwd", "-c", default=None, metavar="PATH", help="Set the working directory.")
@click.option(
    "--prompt",
    "-p",
    default=None,
    metavar="TEXT",
    help="Run a single prompt in non-interactive mode.",
)
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(_OUTPUT_FORMATS),
    default="text",
    show_default=True,
    help="Output format for non-interactive mode (text, json).",
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False, help="Hide spinner in non-interactive mode."
)
@click.option("--provider", default=None, help="Provider to use (e.g. groq, mistral, openrouter).")
@click.option(
    "--model",
    default=None,
    help="Model ID, or provider/model shorthand (e.g. groq/llama-3.3-70b-versatile).",
)
@click.option(
    "--theme",
    "-t",
    default=None,
    metavar="NAME",
    help=(
        "UI theme name (default: dark). Builtins: dark, light. See /theme for all installed themes."
    ),
)
@click.option(
    "--resume",
    "-r",
    default=None,
    metavar="[ID]",
    help="Resume a session. Omit an ID to resume the most recent; pass an ID for a specific session.",
)
@click.option(
    "--system",
    "-s",
    default=None,
    metavar="TEXT",
    help="Inject additional text into the system prompt.",
)
@click.option(
    "--ephemeral", "-e", is_flag=True, default=False, help="Don't save this session to disk."
)
@click.option(
    "--print", "print_flag", is_flag=True, default=False, help="Shorthand for --mode print."
)
@click.option(
    "--mode",
    type=click.Choice(_MODES),
    default=None,
    help="Run mode: interactive (default), print, json, rpc.",
)
@click.option(
    "--no-context-files",
    "-nc",
    is_flag=True,
    default=False,
    help="Disable AGENTS.md and CLAUDE.md discovery and loading.",
)
@click.option(
    "--approve",
    "-a",
    is_flag=True,
    default=False,
    help="Trust project-local files (extensions, settings, context files).",
)
@click.option(
    "--no-approve",
    "-na",
    is_flag=True,
    default=False,
    help="Don't trust project-local files (opposite of --approve).",
)
@click.pass_context
def cli(
    ctx: click.Context,
    version: bool,
    debug: bool,
    cwd: str | None,
    prompt: str | None,
    output_format: str,
    quiet: bool,
    provider: str | None,
    model: str | None,
    theme: str | None,
    resume: str | None,
    system: str | None,
    ephemeral: bool,
    print_flag: bool,
    mode: str | None,
    no_context_files: bool,
    approve: bool,
    no_approve: bool,
) -> None:
    """Tau — an AI coding agent in your terminal."""
    if version:
        click.echo(get_app_version())
        return

    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

    if cwd:
        os.chdir(cwd)

    ctx.ensure_object(dict)
    ctx.obj["prompt"] = prompt
    ctx.obj["provider"] = provider
    ctx.obj["model"] = model
    ctx.obj["theme"] = theme
    ctx.obj["resume"] = resume
    ctx.obj["system"] = system or ""
    ctx.obj["ephemeral"] = ephemeral
    ctx.obj["quiet"] = quiet
    ctx.obj["mode"] = resolve_mode(mode, print_flag, prompt, output_format)
    ctx.obj["no_context_files"] = no_context_files
    ctx.obj["approve"] = approve
    ctx.obj["no_approve"] = no_approve

    if ctx.invoked_subcommand is None:
        asyncio.run(_start(ctx.obj))


_RESUME_LATEST = "__LATEST__"


def _resolve_session_file(resume_id: str) -> Path:
    """Find a session file by its ID, searching all project session directories."""
    from tau.settings.paths import get_sessions_dir

    matches = list(get_sessions_dir().rglob(f"*{resume_id}*.jsonl"))
    if not matches:
        raise click.ClickException(f"No session found with ID: {resume_id}")
    if len(matches) > 1:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0].resolve()


async def _start(opts: dict) -> None:
    """Start the runtime with the given options and run in the specified mode."""
    from tau.runtime.service import Runtime
    from tau.runtime.types import RuntimeConfig

    resolved_provider, resolved_model = resolve_model(opts["model"], opts["provider"])

    resume_value: str | None = opts.get("resume")
    resume_latest = resume_value == _RESUME_LATEST
    session_file: Path | None = None
    if resume_value and not resume_latest:
        session_file = _resolve_session_file(resume_value)

    # Determine project trust from flags
    project_trusted = None
    if opts.get("approve"):
        project_trusted = True
    elif opts.get("no_approve"):
        project_trusted = False

    config = RuntimeConfig(
        cwd=Path.cwd(),
        model_id=resolved_model,
        provider=resolved_provider,
        resume=resume_latest,
        session_file=session_file,
        persist_session=not opts["ephemeral"],
        mode=opts["mode"],
        system_prompt=opts.get("system", ""),
        disable_context_files=opts.get("no_context_files", False),
        project_trusted=project_trusted,
    )

    runtime = await Runtime.create(config)

    try:
        match opts["mode"]:
            case "interactive":
                await _run_interactive(runtime, opts["theme"])
            case "print":
                await _run_print(runtime, opts["prompt"], quiet=opts.get("quiet", False))
            case "json":
                await _run_json(runtime, opts["prompt"], quiet=opts.get("quiet", False))
            case "rpc":
                from tau.rpc.mode import run_rpc_mode

                await run_rpc_mode(runtime)
    finally:
        # Emit `runtime_stop` once, in every mode, on the way out — symmetric to
        # the `runtime_ready` fired in Runtime.create.
        await runtime.ashutdown()


async def _run_interactive(runtime: Runtime, theme: str | None) -> None:
    """Run the interactive TUI mode."""
    from tau.tui.app import App

    app = await App.create(runtime, theme=theme)
    await app.run()


async def _run_print(runtime: Runtime, message: str | None, quiet: bool = False) -> None:
    """Run in print mode: send a message and print the response."""
    if not message:
        raise click.ClickException(
            'A message is required in print mode. Usage: tau --print "your prompt"'
        )

    from tau.message.types import AssistantMessage

    result: AssistantMessage | None = None
    settled = asyncio.Event()

    async def on_message_end(event: object) -> None:
        """Capture the final assistant message."""
        nonlocal result
        msg = getattr(event, "message", None)
        if isinstance(msg, AssistantMessage):
            result = msg

    async def on_settled(_event: object) -> None:
        """Signal that processing is complete."""
        settled.set()

    hooks = runtime.hooks
    unsub_msg = hooks.register("message_end", on_message_end)
    unsub_settled = hooks.register("settled", on_settled)

    try:
        await runtime.invoke(message)
        await settled.wait()
    finally:
        unsub_msg()
        unsub_settled()

    if result is None:
        raise click.ClickException("No response received.")

    for content in result.contents:
        if hasattr(content, "text"):
            click.echo(content.text, nl=False)


async def _run_json(runtime: Runtime, message: str | None, quiet: bool = False) -> None:
    """Run in JSON mode: send a message and return structured JSON output."""
    if not message:
        raise click.ClickException(
            'A message is required in json mode. Usage: tau --mode json "your prompt"'
        )

    import dataclasses
    import json

    from tau.hooks.types import SettledEvent

    settled = asyncio.Event()

    def _serialize(event: object) -> str:
        if dataclasses.is_dataclass(event) and not isinstance(event, type):
            return json.dumps(dataclasses.asdict(event))
        return json.dumps({"type": type(event).__name__})

    async def on_event(event: object) -> None:
        """Output event as JSON and signal when settled."""
        click.echo(_serialize(event))
        if isinstance(event, SettledEvent):
            settled.set()

    hooks = runtime.hooks
    hook_names = [
        "agent_start",
        "agent_end",
        "message_start",
        "message_update",
        "message_end",
        "tool_execution_start",
        "tool_execution_end",
        "settled",
    ]
    unsubs = [hooks.register(name, on_event) for name in hook_names]

    try:
        await runtime.invoke(message)
        await settled.wait()
    finally:
        for unsub in unsubs:
            unsub()


cli.add_command(auth)
cli.add_command(install)
cli.add_command(remove)
cli.add_command(update)
cli.add_command(list_packages, name="list")


def _rewrite_resume_arg(argv: list[str]) -> list[str]:
    """Make --resume [ID] work as an optional-value option.

    click only supports required or absent values for options, so we pre-process
    sys.argv before click sees it:
      --resume         → --resume __LATEST__   (resume most recent)
      --resume <id>    → --resume <id>          (resume specific session)
    """
    out: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--resume", "-r"):
            out.append("--resume")
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                out.append(argv[i + 1])
                i += 2
            else:
                out.append(_RESUME_LATEST)
                i += 1
        else:
            out.append(arg)
            i += 1
    return out


def main() -> None:
    """Entry point for the CLI."""
    import sys

    sys.argv[1:] = _rewrite_resume_arg(sys.argv[1:])
    cli()
