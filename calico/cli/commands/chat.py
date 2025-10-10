"""Interactive chat command for GPT."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt

console = Console()


@click.command(name="chat")
@click.option("--session-id", help="Resume existing session")
@click.option("--model", default="gpt-4o", help="GPT model to use")
@click.option("--temperature", type=float, default=0.2, help="Temperature for GPT")
@click.option("--stream", is_flag=True, help="Enable streaming responses")
def chat_command(session_id: Optional[str], model: str, temperature: float, stream: bool):
    """
    Interactive chat with GPT for automation planning.
    
    This command lets you have a conversation with GPT to plan and execute
    browser automation tasks. You can send prompts, see GPT's reasoning,
    and watch as actions are planned.
    """
    asyncio.run(_run_chat(session_id, model, temperature, stream))


async def _run_chat(session_id: Optional[str], model: str, temperature: float, stream: bool):
    """Run the interactive chat session."""
    console.clear()
    
    # Display welcome banner
    welcome = Panel(
        "[bold cyan]Calico GPT Chat[/bold cyan]\n\n"
        "Interactive session for planning browser automation.\n"
        f"Model: [yellow]{model}[/yellow] | Temperature: [yellow]{temperature}[/yellow]\n\n"
        "[dim]Type 'exit' to quit, 'help' for commands[/dim]",
        border_style="cyan",
        expand=False
    )
    console.print(welcome)
    console.print()
    
    # Initialize GPT client
    try:
        from calico.agent.llm import OpenAILLMClient
        llm_client = OpenAILLMClient(model=model, temperature=temperature)
        console.print("[green]✓[/green] GPT client initialized")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize GPT client: {e}")
        return
    
    console.print()
    
    # Track conversation history
    turn = 0
    state = {"turns": 0, "history": []}
    
    while True:
        # Get user input
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Exiting chat...[/yellow]")
            break
        
        # Handle special commands
        if user_input.lower() in ["exit", "quit", "q"]:
            console.print("[yellow]Goodbye![/yellow]")
            break
        
        if user_input.lower() == "help":
            _show_help()
            continue
        
        if user_input.lower() == "clear":
            console.clear()
            continue
        
        if user_input.lower() == "status":
            _show_status(state, turn)
            continue
        
        if not user_input.strip():
            continue
        
        # Process the prompt
        turn += 1
        state["turns"] = turn
        
        console.print()
        with console.status(f"[bold blue]GPT is thinking... (Turn {turn})[/bold blue]"):
            try:
                # Call GPT with the prompt
                plan = await llm_client.plan_actions(
                    goal=user_input,
                    context={"url": "interactive_chat", "turn": turn},
                    state=state,
                )
                
                # Display the response
                _display_plan(plan, turn)
                
                # Update history
                state["history"].append({
                    "turn": turn,
                    "goal": user_input,
                    "actions": [action.to_dict() for action in plan.actions],
                    "reasoning": plan.reasoning,
                    "done": plan.done
                })
                
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                console.print(f"[dim]Details: {type(e).__name__}[/dim]")


def _display_plan(plan, turn: int):
    """Display the GPT plan in a nice format."""
    # Display reasoning
    if plan.reasoning:
        console.print(Panel(
            Markdown(plan.reasoning),
            title=f"[bold cyan]GPT Reasoning (Turn {turn})[/bold cyan]",
            border_style="cyan",
            expand=False
        ))
        console.print()
    
    # Display actions
    if plan.actions:
        action_table = Table(
            title=f"Planned Actions ({len(plan.actions)})",
            show_header=True,
            header_style="bold magenta",
            border_style="magenta"
        )
        action_table.add_column("#", style="dim", width=3)
        action_table.add_column("Type", style="cyan")
        action_table.add_column("Target", style="yellow")
        action_table.add_column("Value", style="green")
        action_table.add_column("Confidence", style="blue", justify="right")
        
        for i, action in enumerate(plan.actions, 1):
            confidence = f"{action.confidence:.2%}" if action.confidence else "N/A"
            action_table.add_row(
                str(i),
                action.type,
                action.target[:50] + "..." if len(action.target) > 50 else action.target,
                (action.value[:30] + "...") if action.value and len(action.value) > 30 else (action.value or ""),
                confidence
            )
        
        console.print(action_table)
        console.print()
    
    # Display done status
    if plan.done:
        console.print("[bold green]✓ Task marked as complete[/bold green]")
    else:
        console.print("[dim]Task in progress...[/dim]")
    
    # Display raw response (optional, for debugging)
    if plan.raw and False:  # Set to True for debugging
        console.print("\n[dim]Raw response:[/dim]")
        console.print(Panel(plan.raw[:500] + "...", border_style="dim"))


def _show_help():
    """Show help information."""
    help_text = """
[bold cyan]Available Commands:[/bold cyan]

[yellow]exit, quit, q[/yellow]  - Exit the chat
[yellow]help[/yellow]           - Show this help message
[yellow]clear[/yellow]          - Clear the screen
[yellow]status[/yellow]         - Show current session status

[bold cyan]Usage:[/bold cyan]

Simply type your automation goal and press Enter.
GPT will analyze your request and plan the necessary actions.

[bold cyan]Examples:[/bold cyan]

• "Navigate to google.com and search for Python tutorials"
• "Fill out the login form with email test@example.com"
• "Click the submit button and wait for the results"
"""
    console.print(Panel(help_text, border_style="cyan", expand=False))


def _show_status(state: dict, turn: int):
    """Show current session status."""
    status_table = Table(title="Session Status", border_style="blue")
    status_table.add_column("Metric", style="cyan")
    status_table.add_column("Value", style="yellow")
    
    status_table.add_row("Current Turn", str(turn))
    status_table.add_row("Total Actions Planned", str(sum(len(h.get("actions", [])) for h in state["history"])))
    status_table.add_row("History Entries", str(len(state["history"])))
    
    console.print()
    console.print(status_table)
