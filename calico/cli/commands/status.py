"""Status monitoring commands."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

console = Console()


@click.command(name="status")
@click.option("--session-id", help="Show status for specific session")
@click.option("--watch", is_flag=True, help="Watch status in real-time")
@click.option("--efficiency", is_flag=True, help="Show efficiency metrics")
def status_command(session_id: Optional[str], watch: bool, efficiency: bool):
    """
    Show automation status and efficiency metrics.
    
    Monitor running sessions, see GPT response efficiency,
    and track action execution rates.
    """
    if watch:
        asyncio.run(_watch_status(session_id, efficiency))
    else:
        asyncio.run(_show_status(session_id, efficiency))


async def _show_status(session_id: Optional[str], efficiency: bool):
    """Show current status."""
    console.print(Panel(
        "[bold cyan]Calico Automation Status[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Mock data - in real implementation, this would fetch from API/DB
    status_data = _get_status_data(session_id)
    
    # Display sessions table
    sessions_table = Table(
        title="Active Sessions",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan"
    )
    sessions_table.add_column("Session ID", style="yellow")
    sessions_table.add_column("Goal", style="white")
    sessions_table.add_column("Status", style="green")
    sessions_table.add_column("Progress", justify="right")
    sessions_table.add_column("Duration")
    
    for session in status_data.get("sessions", []):
        sessions_table.add_row(
            session["id"][:8],
            session["goal"][:40],
            session["status"],
            f"{session['progress']}%",
            session["duration"]
        )
    
    console.print(sessions_table)
    console.print()
    
    if efficiency:
        _show_efficiency_metrics(status_data)


async def _watch_status(session_id: Optional[str], efficiency: bool):
    """Watch status in real-time."""
    console.print("[cyan]Starting real-time monitoring... Press Ctrl+C to stop[/cyan]\n")
    
    with Live(console=console, refresh_per_second=2) as live:
        try:
            while True:
                # Create layout
                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="sessions"),
                )
                
                if efficiency:
                    layout["sessions"].split_row(
                        Layout(name="session_list"),
                        Layout(name="efficiency")
                    )
                
                # Update content
                status_data = _get_status_data(session_id)
                
                # Header
                layout["header"].update(
                    Panel(
                        f"[bold cyan]Live Status Monitor[/bold cyan] | "
                        f"Updated: {datetime.now().strftime('%H:%M:%S')}",
                        border_style="cyan"
                    )
                )
                
                # Sessions
                sessions_table = _create_sessions_table(status_data)
                if efficiency:
                    layout["sessions"]["session_list"].update(Panel(sessions_table, title="Sessions"))
                    layout["sessions"]["efficiency"].update(Panel(_create_efficiency_panel(status_data), title="Efficiency"))
                else:
                    layout["sessions"].update(Panel(sessions_table, title="Active Sessions"))
                
                live.update(layout)
                await asyncio.sleep(0.5)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")


def _create_sessions_table(status_data: dict) -> Table:
    """Create sessions table."""
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("ID", style="yellow", width=10)
    table.add_column("Status", style="green", width=12)
    table.add_column("Progress", justify="right", width=10)
    table.add_column("Actions", justify="right", width=8)
    
    for session in status_data.get("sessions", []):
        table.add_row(
            session["id"][:8],
            session["status"],
            f"{session['progress']}%",
            str(session.get("actions_count", 0))
        )
    
    return table


def _create_efficiency_panel(status_data: dict) -> Table:
    """Create efficiency metrics table."""
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow", justify="right")
    
    metrics = status_data.get("efficiency", {})
    table.add_row("Avg Response Time", f"{metrics.get('avg_response_time', 0):.2f}s")
    table.add_row("Token Efficiency", f"{metrics.get('token_efficiency', 0):.1%}")
    table.add_row("Action Success Rate", f"{metrics.get('action_success_rate', 0):.1%}")
    table.add_row("GPT API Calls", str(metrics.get('api_calls', 0)))
    table.add_row("Total Tokens", f"{metrics.get('total_tokens', 0):,}")
    
    return table


def _show_efficiency_metrics(status_data: dict):
    """Show detailed efficiency metrics."""
    console.print(Panel(
        "[bold cyan]Efficiency Metrics[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    metrics = status_data.get("efficiency", {})
    
    # Main metrics table
    metrics_table = Table(
        show_header=True,
        header_style="bold magenta",
        border_style="magenta"
    )
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="yellow", justify="right")
    metrics_table.add_column("Trend", style="green")
    
    metrics_table.add_row(
        "Average GPT Response Time",
        f"{metrics.get('avg_response_time', 0):.2f}s",
        "↑ 5%" if metrics.get('response_time_trend', 0) > 0 else "↓ 3%"
    )
    metrics_table.add_row(
        "Token Efficiency",
        f"{metrics.get('token_efficiency', 0):.1%}",
        "→ Stable"
    )
    metrics_table.add_row(
        "Action Success Rate",
        f"{metrics.get('action_success_rate', 0):.1%}",
        "↑ 12%"
    )
    metrics_table.add_row(
        "Match Accuracy",
        f"{metrics.get('match_accuracy', 0):.1%}",
        "↑ 8%"
    )
    
    console.print(metrics_table)
    console.print()
    
    # Token usage breakdown
    token_table = Table(
        title="Token Usage Breakdown",
        show_header=True,
        header_style="bold blue",
        border_style="blue"
    )
    token_table.add_column("Category", style="cyan")
    token_table.add_column("Tokens", justify="right", style="yellow")
    token_table.add_column("% of Total", justify="right", style="green")
    
    token_data = metrics.get("token_breakdown", {})
    total_tokens = metrics.get('total_tokens', 1)
    
    token_table.add_row("Input (Prompts)", f"{token_data.get('input', 0):,}", f"{token_data.get('input', 0)/total_tokens:.1%}")
    token_table.add_row("Output (Completions)", f"{token_data.get('output', 0):,}", f"{token_data.get('output', 0)/total_tokens:.1%}")
    token_table.add_row("Context", f"{token_data.get('context', 0):,}", f"{token_data.get('context', 0)/total_tokens:.1%}")
    
    console.print(token_table)


def _get_status_data(session_id: Optional[str]) -> dict:
    """Get status data - mock implementation."""
    # In real implementation, this would fetch from API or database
    return {
        "sessions": [
            {
                "id": "sess_abc123",
                "goal": "Search for Python tutorials on Google",
                "status": "Running",
                "progress": 65,
                "duration": "1m 23s",
                "actions_count": 8
            },
            {
                "id": "sess_def456",
                "goal": "Fill out job application form",
                "status": "Completed",
                "progress": 100,
                "duration": "3m 45s",
                "actions_count": 15
            }
        ],
        "efficiency": {
            "avg_response_time": 2.3,
            "token_efficiency": 0.78,
            "action_success_rate": 0.92,
            "match_accuracy": 0.88,
            "api_calls": 45,
            "total_tokens": 125000,
            "response_time_trend": 0.05,
            "token_breakdown": {
                "input": 75000,
                "output": 35000,
                "context": 15000
            }
        }
    }
