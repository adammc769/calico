"""Run automation with GPT and monitor progress."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()


@click.command(name="run")
@click.argument("goal")
@click.option("--url", help="Starting URL for automation")
@click.option("--model", default="gpt-4o", help="GPT model to use")
@click.option("--max-turns", type=int, default=8, help="Maximum turns for automation")
@click.option("--headless/--headed", default=True, help="Run browser in headless mode")
@click.option("--watch", is_flag=True, help="Watch execution in real-time")
@click.option("--session-id", help="Resume existing session")
def run_command(goal: str, url: Optional[str], model: str, max_turns: int, headless: bool, watch: bool, session_id: Optional[str]):
    """
    Run an automation task with GPT planning.
    
    GOAL: The automation goal in natural language.
    
    Examples:
    
      calico-gpt run "Search for Python on Google"
      
      calico-gpt run "Apply for jobs on LinkedIn" --url https://linkedin.com --watch
    """
    asyncio.run(_run_automation(goal, url, model, max_turns, headless, watch, session_id))


async def _run_automation(goal: str, url: Optional[str], model: str, max_turns: int, headless: bool, watch: bool, session_id: Optional[str]):
    """Run the automation with live monitoring."""
    console.print(Panel(
        f"[bold cyan]Starting Automation[/bold cyan]\n\n"
        f"Goal: [yellow]{goal}[/yellow]\n"
        f"Model: [yellow]{model}[/yellow]\n"
        f"Max Turns: [yellow]{max_turns}[/yellow]\n"
        f"Headless: [yellow]{headless}[/yellow]",
        border_style="cyan"
    ))
    console.print()
    
    try:
        # Import required components
        from playwright.async_api import async_playwright
        from calico.agent.llm import OpenAILLMClient
        from calico.agent.executor import AIActionExecutor
        from calico.agent.session import AISession
        
        # Initialize components
        with console.status("[bold blue]Initializing GPT and browser..."):
            llm_client = OpenAILLMClient(model=model, temperature=0.2)
            console.print("[green]✓[/green] GPT client initialized")
        
        # Start browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            console.print(f"[green]✓[/green] Browser launched ({'headless' if headless else 'headed'})")
            
            page = await browser.new_page()
            console.print("[green]✓[/green] New page created")
            
            # Navigate to starting URL if provided
            if url:
                await page.goto(url)
                console.print(f"[green]✓[/green] Navigated to {url}")
            
            console.print()
            
            # Use provided session_id or generate one
            import uuid
            actual_session_id = session_id or str(uuid.uuid4())
            
            # Create executor and session
            executor = AIActionExecutor(page, timeout=10.0, session_id=actual_session_id)
            session = AISession(
                llm=llm_client,
                executor=executor,
                max_turns=max_turns,
                max_failures=5
            )
            
            # Run automation with monitoring
            if watch:
                await _run_with_monitoring(session, goal, url or "about:blank")
            else:
                with console.status("[bold blue]Running automation..."):
                    result = await session.run(goal, context={"url": url or "about:blank"})
                
                # Display results
                _display_results(result)
            
            await browser.close()
            console.print("\n[green]✓[/green] Browser closed")
    
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def _run_with_monitoring(session, goal: str, url: str):
    """Run automation with real-time monitoring."""
    from calico.agent.state import SessionState
    
    # Create custom monitoring
    state = SessionState(goal=goal)
    
    with Live(console=console, refresh_per_second=4) as live:
        try:
            # This is a simplified version - full implementation would need hooks into session
            result = await session.run(goal, context={"url": url})
            _display_results(result)
        except Exception as e:
            console.print(f"\n[red]Error during execution:[/red] {e}")


def _display_results(result):
    """Display automation results."""
    console.print()
    console.print(Panel(
        "[bold cyan]Automation Complete[/bold cyan]",
        border_style="cyan"
    ))
    
    # Create results table
    results_table = Table(show_header=False, border_style="blue")
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Value", style="yellow")
    
    results_table.add_row("Goal", result.goal)
    results_table.add_row("Turns", str(result.turns))
    results_table.add_row("Actions Executed", str(len(result.history)))
    results_table.add_row("Success Rate", f"{result.success_rate:.1%}" if hasattr(result, 'success_rate') else "N/A")
    results_table.add_row("Completed", "✓ Yes" if result.done else "✗ No")
    
    console.print()
    console.print(results_table)
    
    # Show action history
    if result.history:
        console.print()
        history_table = Table(
            title="Action History",
            show_header=True,
            header_style="bold magenta",
            border_style="magenta"
        )
        history_table.add_column("#", width=3)
        history_table.add_column("Action", style="cyan")
        history_table.add_column("Target", style="yellow")
        history_table.add_column("Result", style="green")
        
        for i, entry in enumerate(result.history[-10:], 1):  # Show last 10
            action = entry.get("action", {})
            result_status = "✓" if entry.get("success") else "✗"
            history_table.add_row(
                str(i),
                action.get("type", "unknown"),
                action.get("target", "")[:40],
                result_status
            )
        
        console.print(history_table)
