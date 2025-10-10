"""Prompt mode for Calico - direct interaction with a session."""
from __future__ import annotations

import asyncio
import sys
import signal
import logging
from typing import Optional
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.table import Table

from .session_manager import SessionManager, SessionStatus

console = Console()
logger = logging.getLogger(__name__)


CALICO_STYLE = Style.from_dict({
    'prompt': '#00ccff bold',
})


class PromptMode:
    """Prompt mode for direct session interaction."""
    
    def __init__(self, session_id: int, goal: Optional[str] = None):
        self.session_id = session_id
        self.initial_goal = goal
        self.console = Console()
        self.running = True
        self.session_manager = SessionManager.get_instance()
        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            style=CALICO_STYLE,
        )
        
    def show_header(self):
        """Display prompt mode header."""
        session = self.session_manager.get_session(self.session_id)
        status_text = session.status.value if session else "unknown"
        
        header = Panel(
            f"[bold cyan]🎯 Prompt Mode - Session {self.session_id}[/bold cyan]\n\n"
            f"Status: [yellow]{status_text}[/yellow]\n"
            f"[dim]Enter prompts to interact with this session\n"
            f"Ctrl+C to return to CLI mode[/dim]",
            border_style="cyan",
            expand=False
        )
        self.console.print(header)
        self.console.print()
    
    async def display_live_output(self, session):
        """Display live output from the session."""
        layout = Layout()
        layout.split_column(
            Layout(name="status", size=3),
            Layout(name="logs", size=20),
        )
        
        def make_status_panel():
            status_table = Table.grid(padding=(0, 2))
            status_table.add_column(style="cyan")
            status_table.add_column(style="yellow")
            
            status_table.add_row("Session", str(session.session_id))
            status_table.add_row("Status", session.status.value)
            if session.goal:
                status_table.add_row("Goal", session.goal[:60] + "..." if len(session.goal) > 60 else session.goal)
            
            return Panel(status_table, title="[bold cyan]Session Status[/bold cyan]", border_style="cyan")
        
        def make_logs_panel():
            log_text = Text()
            
            # Show last 10 logs from each category
            recent_gpt = session.gpt_logs[-5:] if session.gpt_logs else []
            recent_playwright = session.playwright_logs[-5:] if session.playwright_logs else []
            recent_actions = session.action_logs[-5:] if session.action_logs else []
            
            if recent_gpt:
                log_text.append("GPT Logs:\n", style="bold cyan")
                for log in recent_gpt:
                    log_text.append(f"  {log}\n", style="cyan")
                log_text.append("\n")
            
            if recent_playwright:
                log_text.append("Playwright Logs:\n", style="bold blue")
                for log in recent_playwright:
                    log_text.append(f"  {log}\n", style="blue")
                log_text.append("\n")
            
            if recent_actions:
                log_text.append("Action Logs:\n", style="bold green")
                for log in recent_actions:
                    log_text.append(f"  {log}\n", style="green")
            
            return Panel(log_text, title="[bold yellow]Live Logs[/bold yellow]", border_style="yellow")
        
        layout["status"].update(make_status_panel())
        layout["logs"].update(make_logs_panel())
        
        return layout
    
    async def run_goal(self, goal: str):
        """Execute a goal in the session."""
        session = self.session_manager.get_session(self.session_id)
        if not session:
            self.console.print(f"[red]Error:[/red] Session {self.session_id} not found")
            return
        
        self.console.print(f"\n[cyan]🚀 Starting:[/cyan] {goal}\n")
        session.goal = goal
        session.status = SessionStatus.PLANNING
        session.started_at = datetime.now()
        
        # Create execution task
        async def execution_task():
            try:
                from calico.agent.llm import OpenAILLMClient
                import time
                
                session.add_gpt_log(f"Starting GPT planning for goal: {goal}")
                logger.info(f"Session {session.session_id}: Planning started")
                
                llm_client = OpenAILLMClient(model="gpt-4o", temperature=0.2)
                
                start_time = time.perf_counter()
                session.add_gpt_log("Sending request to GPT-4o...")
                
                plan = await llm_client.plan_actions(
                    goal=goal,
                    context={"url": "prompt_mode", "session_id": session.session_id},
                    state={"turns": 0, "history": []}
                )
                
                elapsed = time.perf_counter() - start_time
                session.add_gpt_log(f"Response received in {elapsed:.2f}s")
                session.add_gpt_log(f"GPT Reasoning: {plan.reasoning}")
                session.add_gpt_log(f"Generated {len(plan.actions)} actions")
                
                session.status = SessionStatus.EXECUTING
                session.add_action_log("Starting execution...")
                session.add_playwright_log("Initializing browser...")
                
                # Simulate execution
                for i, action in enumerate(plan.actions, 1):
                    session.add_action_log(f"Action {i}/{len(plan.actions)}: {action.type} - {action.target}")
                    session.add_playwright_log(f"Executing {action.type} on {action.target}")
                    await asyncio.sleep(0.1)
                
                session.add_playwright_log("Execution completed")
                session.status = SessionStatus.COMPLETED
                session.completed_at = datetime.now()
                
            except asyncio.CancelledError:
                session.add_gpt_log("Operation cancelled by user")
                session.status = SessionStatus.CANCELLED
                session.completed_at = datetime.now()
                raise
            except Exception as e:
                session.add_gpt_log(f"Error: {str(e)}")
                session.status = SessionStatus.FAILED
                session.error = str(e)
                session.completed_at = datetime.now()
                logger.error(f"Session {session.session_id} failed: {e}", exc_info=True)
        
        # Run task with live display
        session.task = asyncio.create_task(execution_task())
        
        try:
            with Live(console=self.console, refresh_per_second=2) as live:
                while not session.task.done():
                    layout = await self.display_live_output(session)
                    live.update(layout)
                    await asyncio.sleep(0.5)
                
                # Show final output
                layout = await self.display_live_output(session)
                live.update(layout)
            
            # Show completion status
            if session.status == SessionStatus.COMPLETED:
                self.console.print("\n[green]✓ Task completed successfully[/green]\n")
            elif session.status == SessionStatus.FAILED:
                self.console.print(f"\n[red]✗ Task failed: {session.error}[/red]\n")
            
        except asyncio.CancelledError:
            self.console.print("\n[yellow]⚠️  Task cancelled[/yellow]\n")
        finally:
            session.task = None
    
    async def run(self):
        """Run prompt mode."""
        self.show_header()
        
        # If initial goal provided, execute it
        if self.initial_goal:
            await self.run_goal(self.initial_goal)
            return
        
        # Otherwise, enter interactive prompt mode
        while self.running:
            try:
                session = self.session_manager.get_session(self.session_id)
                if not session:
                    self.console.print(f"[red]Error:[/red] Session {self.session_id} not found")
                    break
                
                # Show current session status
                status_color = "green" if session.status == SessionStatus.COMPLETED else "yellow"
                self.console.print(f"[{status_color}]Session {self.session_id}[/{status_color}] [{session.status.value}]")
                
                # Get user input
                user_input = await asyncio.to_thread(
                    self.prompt_session.prompt,
                    f"prompt[{self.session_id}]> "
                )
                
                if not user_input.strip():
                    continue
                
                # Execute the prompt
                await self.run_goal(user_input.strip())
                
            except KeyboardInterrupt:
                # Ctrl+C in prompt mode: return to CLI mode
                self.console.print("\n[cyan]Returning to CLI mode...[/cyan]")
                self.running = False
                break
            except EOFError:
                self.running = False
                break
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                logger.error(f"Error in prompt mode: {e}", exc_info=True)


def main():
    """Main entry point for prompt mode."""
    # Get session ID from global session manager or create one
    # Check if there's an argument (the goal)
    goal = None
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    
    # For now, use session 1 (we'll integrate with global session manager later)
    session_id = 1
    
    try:
        # Initialize session manager singleton
        SessionManager.initialize_instance()
        manager = SessionManager.get_instance()
        
        # Create session if it doesn't exist
        if not manager.get_session(session_id):
            manager.create_session()
        
        prompt_mode = PromptMode(session_id=session_id, goal=goal)
        asyncio.run(prompt_mode.run())
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        return 0
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.error(f"Fatal error in prompt mode: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
