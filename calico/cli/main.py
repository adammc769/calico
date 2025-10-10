#!/usr/bin/env python3
"""Main CLI entry point for Calico GPT interactions."""
from __future__ import annotations

import sys
import asyncio
import click
from rich.console import Console

from .commands import run, chat, status, logs, config

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0", prog_name="calico")
def cli(ctx):
    """
    Calico GPT CLI - Interactive GPT automation and monitoring.
    
    Talk to GPT, monitor efficiency, watch actions, and track Playwright errors.
    
    Run 'calico' with no arguments to enter interactive mode.
    """
    # If no command provided, start interactive shell
    if ctx.invoked_subcommand is None:
        from .interactive import start_interactive_shell
        try:
            asyncio.run(start_interactive_shell())
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            sys.exit(0)


# Register all commands
cli.add_command(run.run_command)
cli.add_command(chat.chat_command)
cli.add_command(status.status_command)
cli.add_command(logs.logs_command)
cli.add_command(config.config_command)


def main():
    """Entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
