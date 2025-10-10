"""Log viewing and monitoring commands."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live

console = Console()


@click.command(name="logs")
@click.argument("session-id", required=False)
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real-time")
@click.option("--errors-only", is_flag=True, help="Show only errors")
@click.option("--playwright", is_flag=True, help="Show Playwright-specific errors")
@click.option("--gpt", is_flag=True, help="Show GPT interactions only")
@click.option("--actions", is_flag=True, help="Show action execution logs")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def logs_command(session_id: Optional[str], follow: bool, errors_only: bool, playwright: bool, gpt: bool, actions: bool, lines: int):
    """
    View and monitor automation logs.
    
    Watch GPT interactions, action executions, and Playwright errors in real-time.
    
    Examples:
    
      calico-gpt logs                    # Show recent logs
      
      calico-gpt logs sess_123 -f        # Follow logs for session
      
      calico-gpt logs --playwright       # Show Playwright errors only
      
      calico-gpt logs --gpt              # Show GPT interactions
    """
    asyncio.run(_show_logs(session_id, follow, errors_only, playwright, gpt, actions, lines))


async def _show_logs(session_id: Optional[str], follow: bool, errors_only: bool, playwright: bool, gpt: bool, actions: bool, lines: int):
    """Show logs with optional filtering."""
    # Determine filter
    log_filter = "all"
    if playwright:
        log_filter = "playwright"
    elif gpt:
        log_filter = "gpt"
    elif actions:
        log_filter = "actions"
    elif errors_only:
        log_filter = "errors"
    
    # Show header
    title = f"Logs: {session_id or 'All Sessions'}"
    if log_filter != "all":
        title += f" (Filter: {log_filter})"
    
    console.print(Panel(
        f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    if follow:
        await _follow_logs(session_id, log_filter)
    else:
        _show_static_logs(session_id, log_filter, lines)


def _show_static_logs(session_id: Optional[str], log_filter: str, lines: int):
    """Show static log output."""
    # Mock log data - in real implementation, fetch from logging system
    logs = _get_mock_logs(session_id, log_filter, lines)
    
    for log_entry in logs:
        _print_log_entry(log_entry)


async def _follow_logs(session_id: Optional[str], log_filter: str):
    """Follow logs in real-time."""
    console.print("[cyan]Following logs... Press Ctrl+C to stop[/cyan]\n")
    
    try:
        while True:
            # In real implementation, this would stream from logging system
            logs = _get_mock_logs(session_id, log_filter, 5)
            for log_entry in logs:
                _print_log_entry(log_entry)
            
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs[/yellow]")


def _print_log_entry(entry: dict):
    """Print a single log entry with formatting."""
    timestamp = entry.get("timestamp", "")
    level = entry.get("level", "INFO")
    source = entry.get("source", "")
    message = entry.get("message", "")
    
    # Color by level
    level_colors = {
        "DEBUG": "dim",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red"
    }
    level_color = level_colors.get(level, "white")
    
    # Format source
    source_display = f"[cyan]{source}[/cyan]" if source else ""
    
    # Print the log line
    console.print(
        f"[dim]{timestamp}[/dim] "
        f"[{level_color}]{level:8}[/{level_color}] "
        f"{source_display} "
        f"{message}"
    )
    
    # Show additional details for errors
    if level in ["ERROR", "CRITICAL"] and "details" in entry:
        console.print(f"  [dim]{entry['details']}[/dim]")
    
    # Show action details
    if "action" in entry:
        action = entry["action"]
        console.print(f"  → Action: [cyan]{action.get('type')}[/cyan] on [yellow]{action.get('target', '')}[/yellow]")
    
    # Show GPT details
    if "gpt_details" in entry:
        details = entry["gpt_details"]
        if "tokens" in details:
            console.print(f"  → Tokens: [yellow]{details['tokens']}[/yellow] | Response time: [yellow]{details.get('response_time', 0):.2f}s[/yellow]")


def _get_mock_logs(session_id: Optional[str], log_filter: str, lines: int) -> list[dict]:
    """Get mock log data - replace with real logging system."""
    base_logs = [
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "source": "GPT",
            "message": "Planning actions for goal: Search for Python tutorials",
            "gpt_details": {"tokens": 1250, "response_time": 2.3}
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "source": "Executor",
            "message": "Executing action: goto",
            "action": {"type": "goto", "target": "https://google.com"}
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "source": "Executor",
            "message": "Executing action: fill",
            "action": {"type": "fill", "target": "input[name='q']", "value": "Python tutorials"}
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "ERROR",
            "source": "Playwright",
            "message": "Timeout waiting for selector: button[type='submit']",
            "details": "Selector not found after 5000ms"
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "source": "Executor",
            "message": "Retrying action with fallback selector",
            "action": {"type": "click", "target": "button:has-text('Search')"}
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "INFO",
            "source": "GPT",
            "message": "Task completed successfully",
            "gpt_details": {"tokens": 890, "response_time": 1.8}
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "WARNING",
            "source": "Session",
            "message": "High action retry rate detected",
            "details": "3 out of 8 actions required retries"
        },
        {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": "DEBUG",
            "source": "MCP",
            "message": "Screenshot captured successfully",
        },
    ]
    
    # Filter logs
    if log_filter == "playwright":
        filtered = [log for log in base_logs if log.get("source") == "Playwright" or "playwright" in log.get("message", "").lower()]
    elif log_filter == "gpt":
        filtered = [log for log in base_logs if log.get("source") == "GPT" or "gpt_details" in log]
    elif log_filter == "actions":
        filtered = [log for log in base_logs if "action" in log]
    elif log_filter == "errors":
        filtered = [log for log in base_logs if log.get("level") in ["ERROR", "CRITICAL", "WARNING"]]
    else:
        filtered = base_logs
    
    return filtered[:lines]
