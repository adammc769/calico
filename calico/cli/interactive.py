"""Interactive CLI for Calico GPT - CLI-first with prompt mode."""
from __future__ import annotations

import asyncio
import sys
import signal
import logging
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.spinner import Spinner
from rich.status import Status

from .session_manager import SessionManager, SessionStatus, SessionInfo

console = Console()
logger = logging.getLogger(__name__)


# Custom style for prompt_toolkit with proper contrast
CALICO_STYLE = Style.from_dict({
    'completion-menu.completion': 'bg:#1e1e1e #ffffff',
    'completion-menu.completion.current': 'bg:#0066cc #ffffff',  # Blue background for selected
    'completion-menu.meta.completion': 'bg:#1e1e1e #888888',
    'completion-menu.meta.completion.current': 'bg:#0066cc #ffffff',
    'scrollbar.background': 'bg:#333333',
    'scrollbar.button': 'bg:#666666',
})


class CalicoCompleter(Completer):
    """Auto-completion for Calico commands."""
    
    COMMANDS = {
        '/prompt': 'Execute goal or enter prompt mode',
        '/session': 'Switch to session <num>',
        '/watch': 'Watch session output',
        '/logs': 'Show logs (all/server/gpt/actions/playwright)',
        '/models': 'Display all available models',
        '/stop': 'Stop session(s)',
        '/efficiency': 'Show efficiency overview',
        '/background': 'Background Calico',
        '/status': 'Show current status',
        '/config': 'Manage configuration',
        '/help': 'Show help',
        '/exit': 'Exit Calico',
        '/quit': 'Exit Calico',
        '/clear': 'Clear screen',
    }
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        if text.startswith('/'):
            # Complete / commands
            for cmd, desc in self.COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc
                    )


class CalicoShell:
    """Interactive Calico CLI with multi-session support."""
    
    def __init__(self):
        # Create key bindings for ESC key
        kb = KeyBindings()
        
        @kb.add('escape')
        def _(event):
            """ESC key pressed - stop current operation."""
            event.app.exit(result='__ESC__')
        
        self.session_prompt = PromptSession(
            history=InMemoryHistory(),
            completer=CalicoCompleter(),
            style=CALICO_STYLE,
            key_bindings=kb,
        )
        self.console = Console()
        self.running = True
        
        # Use singleton session manager
        self.session_manager = SessionManager.initialize_instance(max_sessions=9)
        
        # Create initial session
        self.session_manager.create_session()
        
        self.current_context = {
            'model': 'gpt-4o',
            'temperature': 0.2,
        }
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        pass
        
    def show_welcome(self):
        """Display welcome banner."""
        self.console.clear()
        
        welcome = Panel(
            f"[bold cyan]🤖 Calico CLI[/bold cyan]\n\n"
            f"Active CLI for GPT-powered browser automation.\n\n"
            f"[yellow]All commands start with [bold]/[/bold][/yellow]\n\n"
            f"[cyan]Common Commands:[/cyan]\n"
            f"  • [bold]/prompt \"goal\"[/bold] - Execute goal in current session\n"
            f"  • [bold]/prompt[/bold] - Enter interactive prompt mode\n"
            f"  • [bold]/session 2[/bold] - Switch to session 2\n"
            f"  • [bold]/watch 1[/bold] - Watch session 1\n"
            f"  • [bold]/logs all[/bold] - View all logs\n"
            f"  • [bold]/models[/bold] - Show available models\n"
            f"  • [bold]/efficiency[/bold] - Show efficiency metrics\n"
            f"  • [bold]/status[/bold] - Show session status\n"
            f"  • [bold]/help[/bold] - Show all commands\n"
            f"  • [bold]/exit[/bold] - Exit Calico\n\n"
            f"[dim]Type / and press Tab for command completion[/dim]",
            border_style="cyan",
            expand=False
        )
        self.console.print(welcome)
        self.console.print()
        
        # Show session summary at bottom
        self.show_session_summary()
    
    def show_session_summary(self):
        """Display session summary at bottom of screen."""
        sessions = self.session_manager.list_sessions()
        active_id = self.session_manager.active_session_id
        
        if not sessions:
            return
        
        # Current session details
        current_session = self.session_manager.get_active_session()
        if current_session:
            status_style = self._get_session_color(current_session)
            self.console.print(
                f"[{status_style}]● Current Session: {current_session.session_id}[/{status_style}] | "
                f"Status: {current_session.status.value} | "
                f"Completed tasks: {current_session.completed_tasks}"
            )
            self.console.print()
        
        # All sessions summary
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
        table.add_column("ID", style="cyan", width=3)
        table.add_column("Status", width=12)
        table.add_column("Tasks", justify="right", width=6)
        table.add_column("Goal", width=50)
        
        for session in sessions:
            marker = "→" if session.session_id == active_id else " "
            status_color = self._get_session_color(session)
            
            goal_display = (session.goal[:47] + "...") if session.goal and len(session.goal) > 50 else (session.goal or "-")
            
            table.add_row(
                f"{marker}{session.session_id}",
                f"[{status_color}]{session.status.value}[/{status_color}]",
                str(session.completed_tasks),
                goal_display
            )
        
        self.console.print(table)
        self.console.print()
    
    def _get_session_color(self, session: SessionInfo) -> str:
        """Get color for session based on status."""
        if session.status == SessionStatus.FAILED:
            return "red bold"
        elif session.hang_detected or (session.status in [SessionStatus.PLANNING, SessionStatus.EXECUTING]):
            # Check for hang
            session.check_for_hang()
            if session.hang_detected:
                return "yellow bold"
        
        if session.status == SessionStatus.COMPLETED:
            return "green"
        elif session.status in [SessionStatus.PLANNING, SessionStatus.EXECUTING]:
            return "cyan bold"
        
        return "white bold"
    
    def show_help(self):
        """Display help information."""
        help_table = Table(
            title="Available Commands (All start with /)",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan"
        )
        help_table.add_column("Command", style="cyan", width=32)
        help_table.add_column("Description", style="white")
        
        commands = [
            ("[bold]Session & Execution Commands:[/bold]", ""),
            ("/prompt \"<goal>\"", "Execute goal in current session (stay in CLI)"),
            ("/prompt", "Enter interactive prompt mode for current session"),
            ("/session <num>", "Create/switch to session <num> (1-9)"),
            ("/stop <num>", "Stop/end session <num>"),
            ("/stop all", "Stop/end all sessions"),
            ("", ""),
            ("[bold]Monitoring Commands:[/bold]", ""),
            ("/watch <num>", "Watch session <num> output live (stay in CLI)"),
            ("/watch all", "Watch all sessions overview (live)"),
            ("/status", "Show current status and all sessions"),
            ("/efficiency", "Show efficiency metrics (Ctrl+C to return)"),
            ("", ""),
            ("[bold]Logs Commands:[/bold]", ""),
            ("/logs all", "Show all logs for current session"),
            ("/logs server", "Show server logs for all sessions"),
            ("/logs gpt", "Show GPT/LLM logs"),
            ("/logs actions", "Show action execution logs"),
            ("/logs playwright", "Show Playwright browser logs"),
            ("", ""),
            ("[bold]Configuration Commands:[/bold]", ""),
            ("/models", "Display all available models from server"),
            ("/config", "Show current configuration"),
            ("/config set <key> <value>", "Set configuration value"),
            ("", ""),
            ("[bold]System Commands:[/bold]", ""),
            ("/background", "Background Calico (sessions keep running)"),
            ("/clear", "Clear the screen"),
            ("/help", "Show this help message"),
            ("/exit, /quit", "Exit Calico (ends all sessions)"),
            ("", ""),
            ("[bold]Keyboard Shortcuts:[/bold]", ""),
            ("Ctrl+C in CLI mode", "End all sessions and exit"),
            ("Ctrl+C in prompt mode", "Return to CLI mode (session continues)"),
            ("ESC in prompt mode", "Stop current operation"),
            ("Tab", "Auto-complete commands"),
        ]
        
        for cmd, desc in commands:
            help_table.add_row(cmd, desc)
        
        self.console.print()
        self.console.print(help_table)
        self.console.print()
        self.console.print("[dim]Tip: All sessions run on the server. CLI is just a view into them.[/dim]")
        self.console.print()
    
    async def handle_command(self, user_input: str):
        """Handle user commands."""
        stripped = user_input.strip()
        
        if not stripped:
            return
        
        # All commands start with /
        if stripped.startswith('/'):
            await self.handle_slash_command(stripped)
        else:
            # Check if user forgot the / prefix
            first_word = stripped.split()[0] if ' ' in stripped else stripped
            if first_word in ['prompt', 'session', 'watch', 'logs', 'models', 'stop', 'efficiency', 'help', 'status', 'config', 'exit', 'quit']:
                self.console.print(f"[yellow]Did you mean:[/yellow] /{stripped}")
                self.console.print("[dim]All commands start with / (e.g., /prompt, /session, /logs)[/dim]")
            else:
                self.console.print(f"[yellow]Unknown command:[/yellow] {stripped}")
                self.console.print("[dim]Type /help for available commands[/dim]")
                self.console.print("[dim]All commands start with / (e.g., /prompt \"goal\", /help)[/dim]")
    
    async def handle_slash_command(self, cmd: str):
        """Handle all commands (starting with /)."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Session and task commands
        if command == '/prompt':
            await self.handle_prompt(args)
        
        elif command == '/session':
            await self.handle_session(args)
        
        elif command == '/watch':
            await self.handle_watch_session(args)
        
        elif command == '/logs':
            await self.handle_logs(args)
        
        elif command == '/models':
            await self.handle_models()
        
        elif command == '/stop':
            await self.handle_stop(args)
        
        elif command == '/efficiency':
            await self.handle_efficiency()
        
        # System commands
        elif command in ['/exit', '/quit']:
            # End all running sessions before exiting
            active = self.session_manager.get_active_sessions()
            if active:
                self.console.print(f"[yellow]⚠️  Ending {len(active)} running session(s)...[/yellow]")
                await self.session_manager.cancel_all_sessions()
            self.running = False
            self.console.print("[yellow]Goodbye! 👋[/yellow]")
        
        elif command == '/background':
            await self.handle_background()
        
        elif command == '/help':
            self.show_help()
        
        elif command == '/clear':
            self.console.clear()
            self.show_welcome()
        
        elif command == '/status':
            await self.handle_status()
        
        elif command == '/config':
            await self.handle_config(args)
        
        else:
            self.console.print(f"[red]Unknown command:[/red] {command}")
            self.console.print("[dim]Type /help for available commands[/dim]")
    
    async def handle_prompt(self, args: str):
        """Handle /prompt command."""
        if args:
            # Check for verbose/debug flags
            verbose_mode = False
            if args.startswith('--verbose ') or args.startswith('--debug ') or args.startswith('--trace '):
                verbose_mode = True
                # Remove flag from args
                for flag in ['--verbose', '--debug', '--trace']:
                    if args.startswith(flag + ' '):
                        args = args[len(flag):].strip()
                        break
            
            # Get session first
            session = self.session_manager.get_active_session()
            if not session:
                self.console.print("[red]Error:[/red] No active session")
                return
            
            # Store session_id for use in callback closure
            session_id = session.session_id
            
            # Direct execution with goal - use proper agent session
            self.console.print(f"\n[cyan]🚀 Starting:[/cyan] {args}")
            if verbose_mode:
                self.console.print(f"[green]✓[/green] Session initialized (Session ID: {session_id})\n")
            else:
                self.console.print()
            
            # Enable verbose mode on session
            session.verbose_mode = verbose_mode
            session.trace_data = {
                'selectors_tried': [],
                'ocr_detections': [],
                'fuzzy_matches': [],
                'screenshots': 0,
                'retries': 0
            }
            
            # Execute the goal using the proper orchestrator
            session.goal = args
            session.status = SessionStatus.PLANNING
            session.started_at = datetime.now()
            session.add_gpt_log(f"Goal: {args}")
            
            try:
                from calico.workflow.orchestrator import run_agent_session_async
                from calico.workflow.config import get_settings
                import time
                
                settings = get_settings()
                
                if not verbose_mode:
                    with self.console.status("[cyan]Initializing...[/cyan]", spinner="dots"):
                        pass
                    self.console.print("[green]✓[/green] Session initialized\n")
                
                # Use the orchestrator to run the session
                # The orchestrator handles multi-turn conversations, Playwright, etc.
                try:
                    # Prepare LLM config with current model
                    llm_config = {
                        'model': self.current_context['model'],
                        'max_turns': 10,
                        'max_failures': 5
                    }
                    
                    # Create a callback for real-time updates with Rich console
                    # Track last navigation to avoid duplicate messages
                    last_navigation_url = [None]
                    
                    def progress_callback(event_type: str, data: dict):
                        """Handle real-time progress updates with beautiful Rich formatting."""
                        # Playwright browser events
                        if event_type == "playwright.navigation":
                            url = data.get("url", "")
                            # Only show if URL changed (avoid duplicates)
                            if url and url != last_navigation_url[0]:
                                last_navigation_url[0] = url
                                # Truncate long URLs
                                display_url = url[:70] + "..." if len(url) > 70 else url
                                self.console.print(f"[blue]    🌐 Navigated to:[/blue] [dim]{display_url}[/dim]")
                        
                        elif event_type == "playwright.load":
                            url = data.get("url", "")
                            if url:
                                display_url = url[:70] + "..." if len(url) > 70 else url
                                self.console.print(f"[blue]    📄 Page loaded:[/blue] [dim]{display_url}[/dim]")
                        
                        elif event_type == "playwright.console":
                            msg_type = data.get("type", "log")
                            text = data.get("text", "")
                            # Show all console messages in verbose mode, otherwise only errors/warnings
                            if verbose_mode or msg_type in ["error", "warning"]:
                                icon = "❌" if msg_type == "error" else "⚠️" if msg_type == "warning" else "📝"
                                display_text = text[:80] + "..." if len(text) > 80 else text
                                color = "dim red" if msg_type == "error" else "dim yellow" if msg_type == "warning" else "dim white"
                                self.console.print(f"[{color}]    {icon} Console {msg_type}: {display_text}[/{color}]")
                        
                        elif event_type == "playwright.captcha_detected":
                            captcha_type = data.get("type", "unknown")
                            captcha_id = data.get("captcha_id", "")
                            url = data.get("url", "")
                            api_url = data.get("api_url", "")
                            
                            self.console.print(f"\n[bold red]🚨 CAPTCHA DETECTED[/bold red]")
                            self.console.print(f"[yellow]  Type: {captcha_type}[/yellow]")
                            self.console.print(f"[yellow]  URL: {url}[/yellow]")
                            self.console.print(f"[yellow]  Captcha ID: {captcha_id}[/yellow]")
                            self.console.print(f"[cyan]  Session paused - waiting for human to solve captcha[/cyan]")
                            self.console.print(f"[dim]  Check: sessions/{session_id}/captcha/{captcha_id}.png[/dim]\n")
                        
                        elif event_type == "playwright.error":
                            message = data.get("message", "")
                            if message:
                                display_msg = message[:80] + "..." if len(message) > 80 else message
                                self.console.print(f"[red]    ⚠️  Page error: {display_msg}[/red]")
                        
                        elif event_type == "playwright.response":
                            url = data.get("url", "")
                            status = data.get("status", 0)
                            ok = data.get("ok", True)
                            # Only show important responses (errors)
                            if not ok and status >= 400:
                                display_url = url[:50] + "..." if len(url) > 50 else url
                                self.console.print(f"[dim yellow]    ⚠️  HTTP {status}: {display_url}[/dim yellow]")
                        
                        # Session and action events
                        elif event_type == "session_start":
                            received_session_id = data.get("session_id", "unknown")
                            self.console.print(f"\n[dim]Session {received_session_id[:8]}...[/dim]")
                            
                        elif event_type == "turn_start":
                            turn = data.get("turn", 0)
                            self.console.print(f"\n[bold cyan]━━━ Turn {turn} ━━━[/bold cyan]")
                            self.console.print("[cyan]Planning actions...[/cyan]")
                            
                        elif event_type == "reasoning_complete":
                            reasoning = data.get("reasoning", "")
                            actions_planned = data.get("actions_planned", 0)
                            if reasoning:
                                # Show abbreviated reasoning
                                preview = reasoning[:120] + "..." if len(reasoning) > 120 else reasoning
                                self.console.print(f"[dim cyan]💭 {preview}[/dim cyan]")
                            if actions_planned > 0:
                                self.console.print(f"[cyan]📋 Planned {actions_planned} action(s)[/cyan]")
                                
                        elif event_type == "action_start":
                            action = data.get("action", {})
                            action_type = action.get("type", "unknown")
                            target = action.get("target", "")
                            index = data.get("index", 0)
                            total = data.get("total", 0)
                            confidence = action.get("confidence")
                            
                            # Truncate target for display
                            display_target = target[:50] + "..." if len(target) > 50 else target
                            self.console.print(f"[yellow]  ▶ [{index}/{total}] {action_type}[/yellow] → [dim]{display_target}[/dim]")
                            
                            # ALWAYS show confidence if available (not just in verbose mode)
                            if confidence is not None:
                                conf_color = "green" if confidence > 0.8 else "yellow" if confidence > 0.5 else "red"
                                self.console.print(f"[{conf_color}]     Confidence: {confidence:.2f}[/{conf_color}]")
                            
                            # Show selector details in verbose mode
                            if verbose_mode:
                                action_value = action.get("value")
                                if action_value:
                                    val_display = str(action_value)[:50] + "..." if len(str(action_value)) > 50 else str(action_value)
                                    self.console.print(f"[dim]     Value: {val_display}[/dim]")
                                
                                action_meta = action.get("metadata", {})
                                if action_meta:
                                    # Show timeout
                                    if "timeout_ms" in action_meta:
                                        self.console.print(f"[dim]     Timeout: {action_meta['timeout_ms']}ms[/dim]")
                                    # Show any selector strategies
                                    if "selectors" in action_meta:
                                        selectors = action_meta["selectors"]
                                        if isinstance(selectors, list):
                                            self.console.print(f"[dim]     Selectors tried: {len(selectors)}[/dim]")
                            
                        elif event_type == "action_complete":
                            result = data.get("result", {})
                            action = data.get("action", {})
                            success = result.get("success", False)
                            message = result.get("message", "")
                            index = data.get("index", 0)
                            
                            if success:
                                self.console.print(f"[green]    ✓ Success[/green]")
                                
                                # Show extracted text if available
                                action_metadata = action.get("metadata", {})
                                extracted_text = action_metadata.get("extracted_text")
                                
                                # Also check result data for extracted text (new location)
                                result_data = result.get("data", {})
                                if not extracted_text and result_data:
                                    extracted_text = result_data.get("extracted_text")
                                
                                if extracted_text:
                                    text_length = result_data.get("text_length", len(extracted_text))
                                    
                                    if verbose_mode:
                                        # In verbose mode, show more text with proper formatting
                                        self.console.print(f"[bold green]    📝 Extracted Text ({text_length} characters):[/bold green]")
                                        
                                        # Format the text for better readability
                                        # Show first 500 chars with line breaks preserved
                                        formatted_text = extracted_text[:500]
                                        if len(extracted_text) > 500:
                                            formatted_text += f"\n... ({text_length - 500} more characters)"
                                        
                                        # Display in a panel for better visibility
                                        self.console.print(Panel(
                                            formatted_text.strip(),
                                            border_style="green",
                                            padding=(1, 2)
                                        ))
                                    else:
                                        # In normal mode, show preview with length info
                                        text_preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
                                        self.console.print(f"[dim green]    📝 Extracted: {text_preview}[/dim green]")
                                        if len(extracted_text) > 150:
                                            self.console.print(f"[dim]    (Total: {text_length} characters. Use --verbose to see full text)[/dim]")
                                
                                # Show result data if available (candidates, OCR, etc.)
                                if result_data and verbose_mode:
                                    # Show candidates if present
                                    candidates = result_data.get("candidates", [])
                                    if candidates:
                                        self.console.print(f"[dim cyan]    🎯 Found {len(candidates)} candidate(s)[/dim cyan]")
                                        # Show top 5 candidates in verbose mode
                                        for i, cand in enumerate(candidates[:5], 1):
                                            cand_type = cand.get("type", "unknown")
                                            cand_text = cand.get("text", "")[:60]
                                            score = cand.get("score", 0)
                                            confidence = cand.get("confidence", 0)
                                            bbox = cand.get("bbox", {})
                                            self.console.print(f"[dim]      {i}. [{cand_type}] {cand_text}[/dim]")
                                            self.console.print(f"[dim]         Score: {score:.3f}, Confidence: {confidence:.3f}, BBox: {bbox}[/dim]")
                                    
                                    # Show OCR text if present (verbose mode shows more detail)
                                    ocr_text = result_data.get("ocr_text") or result_data.get("ocr")
                                    if ocr_text:
                                        if isinstance(ocr_text, list):
                                            self.console.print(f"[dim magenta]    🔍 OCR: {len(ocr_text)} chunk(s)[/dim magenta]")
                                            # Show more chunks in verbose mode
                                            for i, chunk in enumerate(ocr_text[:5], 1):
                                                if isinstance(chunk, dict):
                                                    chunk_text = chunk.get("text", "")
                                                    conf = chunk.get("confidence", 0)
                                                    bbox = chunk.get("bbox", {})
                                                    chunk_preview = chunk_text[:80] + "..." if len(chunk_text) > 80 else chunk_text
                                                    self.console.print(f"[dim]      {i}. {chunk_preview}[/dim]")
                                                    self.console.print(f"[dim]         Confidence: {conf:.3f}, BBox: {bbox}[/dim]")
                                                else:
                                                    chunk_preview = str(chunk)[:80] + "..." if len(str(chunk)) > 80 else str(chunk)
                                                    self.console.print(f"[dim]      {i}. {chunk_preview}[/dim]")
                                        elif isinstance(ocr_text, str):
                                            ocr_preview = ocr_text[:150] + "..." if len(ocr_text) > 150 else ocr_text
                                            self.console.print(f"[dim magenta]    🔍 OCR: {ocr_preview}[/dim magenta]")
                                    
                                    # Show screenshot info if available
                                    screenshot_path = result_data.get("screenshot_path")
                                    if screenshot_path:
                                        self.console.print(f"[dim blue]    📸 Screenshot: {screenshot_path}[/dim blue]")
                                elif result_data and not verbose_mode:
                                    # In non-verbose mode, show summary with confidence values
                                    candidates = result_data.get("candidates", [])
                                    if candidates:
                                        self.console.print(f"[dim cyan]    🎯 Found {len(candidates)} candidate(s)[/dim cyan]")
                                        # Show top 3 candidates with confidence
                                        for i, cand in enumerate(candidates[:3], 1):
                                            cand_type = cand.get("type", "unknown")
                                            cand_text = cand.get("text", "")[:40]
                                            score = cand.get("score", 0)
                                            confidence = cand.get("confidence", 0)
                                            # Show confidence value as well as score
                                            self.console.print(f"[dim]      {i}. [{cand_type}] {cand_text} | score: {score:.2f}, conf: {confidence:.2f}[/dim]")
                                    
                                    # Show OCR summary with confidence values
                                    ocr_text = result_data.get("ocr_text") or result_data.get("ocr")
                                    if ocr_text:
                                        if isinstance(ocr_text, list):
                                            self.console.print(f"[dim magenta]    🔍 OCR: {len(ocr_text)} chunk(s)[/dim magenta]")
                                            # Show top 2 OCR chunks with confidence in normal mode
                                            for i, chunk in enumerate(ocr_text[:2], 1):
                                                if isinstance(chunk, dict):
                                                    chunk_text = chunk.get("text", "")[:60]
                                                    conf = chunk.get("confidence", 0)
                                                    self.console.print(f"[dim]      {i}. {chunk_text} (conf: {conf:.2f})[/dim]")
                                        elif isinstance(ocr_text, str):
                                            ocr_preview = ocr_text[:100] + "..." if len(ocr_text) > 100 else ocr_text
                                            self.console.print(f"[dim magenta]    🔍 OCR: {ocr_preview}[/dim magenta]")
                            else:
                                # Show error message (truncated)
                                error_msg = message[:120] + "..." if len(message) > 120 else message
                                self.console.print(f"[red]    ✗ Failed: {error_msg}[/red]")
                                
                                # In verbose mode, show more error details
                                if verbose_mode:
                                    result_data = result.get("data", {})
                                    if result_data:
                                        error_type = result_data.get("error_type")
                                        if error_type:
                                            self.console.print(f"[dim red]      Error Type: {error_type}[/dim red]")
                                        action_dict = result_data.get("action", {})
                                        if action_dict:
                                            self.console.print(f"[dim red]      Failed Action: {action_dict.get('type')} on {action_dict.get('target', '')[:50]}[/dim red]")
                                
                        elif event_type == "turn_complete":
                            completed = data.get("completed", False)
                            actions = data.get("actions", 0)
                            success_count = data.get("success_count", 0)
                            
                            if completed:
                                self.console.print(f"\n[bold green]✓ Goal achieved![/bold green]")
                            elif actions > 0:
                                self.console.print(f"[dim]  {success_count}/{actions} actions succeeded[/dim]")
                                
                        elif event_type == "session_complete":
                            status = data.get("status", "unknown")
                            turns = data.get("turns", 0)
                            events = data.get("events", 0)
                            
                            if status == "completed":
                                self.console.print(f"\n[bold green]🎉 Session completed in {turns} turn(s), {events} action(s)[/bold green]")
                            else:
                                self.console.print(f"\n[yellow]⚠️  Session ended after {turns} turn(s)[/yellow]")
                    
                    # Use async version with callback for real-time updates
                    self.console.print()
                    result = await run_agent_session_async(
                        goal=args,
                        agent_name=f"cli_session_{session.session_id}",
                        llm_config=llm_config,
                        raise_on_failure=False,
                        progress_callback=progress_callback  # Enable streaming!
                    )
                    
                    # Display results from the orchestrator
                    self.console.print(f"\n[bold yellow]Session Results:[/bold yellow]")
                    self.console.print("[green]" + "="*60 + "[/green]")
                    
                    if result.completed:
                        self.console.print(f"[green]✓[/green] Task completed successfully")
                        session.status = SessionStatus.COMPLETED
                    else:
                        self.console.print(f"[red]✗[/red] Task failed")
                        session.status = SessionStatus.FAILED
                        if result.final_error:
                            self.console.print(f"[red]Error:[/red] {result.final_error}")
                    
                    # Show reasoning
                    if result.reasoning:
                        self.console.print(f"\n[bold cyan]Reasoning:[/bold cyan]")
                        for i, reason in enumerate(result.reasoning, 1):
                            self.console.print(f"{i}. {reason}")
                    
                    # Show events/actions taken
                    if result.events:
                        self.console.print(f"\n[bold magenta]Actions Taken ({len(result.events)}):[/bold magenta]")
                        for event in result.events[:10]:  # Show first 10
                            action = event.get('action', {})
                            action_type = action.get('type', 'unknown')
                            target = action.get('target', '')
                            self.console.print(f"  • {action_type} → {target}")
                    
                    self.console.print("[green]" + "="*60 + "[/green]\n")
                    
                    session.completed_at = datetime.now()
                    session.increment_completed_tasks()
                    
                    self.console.print("[green]✓ Session completed[/green]\n")
                    self.show_session_summary()
                    
                except asyncio.CancelledError:
                    # Task was cancelled (e.g., user pressed Ctrl+C)
                    session.status = SessionStatus.CANCELLED
                    session.completed_at = datetime.now()
                    self.console.print(f"\n[yellow]⚠️  Task cancelled by user[/yellow]\n")
                    logger.info(f"Session {session.session_id} cancelled by user")
                    # Re-raise to propagate cancellation
                    raise
                except Exception as e:
                    session.status = SessionStatus.FAILED
                    session.error = str(e)
                    session.completed_at = datetime.now()
                    self.console.print(f"[red]Error executing session:[/red] {e}")
                    logger.error(f"Session {session.session_id} failed: {e}", exc_info=True)
                
            except asyncio.CancelledError:
                # Task cancelled - handle gracefully
                session.status = SessionStatus.CANCELLED
                session.completed_at = datetime.now()
                self.console.print(f"\n[yellow]⚠️  Task cancelled[/yellow]\n")
                logger.info(f"Session {session.session_id} cancelled")
            except Exception as e:
                session.status = SessionStatus.FAILED
                session.error = str(e)
                session.completed_at = datetime.now()
                self.console.print(f"[red]Error:[/red] {e}")
                logger.error(f"Session {session.session_id} failed: {e}", exc_info=True)
        else:
            # Enter prompt mode - interactive loop
            self.console.print("\n[bold cyan]Entering Prompt Mode[/bold cyan]\n")
            self.console.print("Type your prompts below. Press Ctrl+C to return to CLI.\n")
            
            session = self.session_manager.get_active_session()
            if not session:
                self.console.print("[red]Error:[/red] No active session")
                return
            
            # Interactive prompt loop
            prompt_active = True
            current_task = None
            while prompt_active:
                try:
                    user_prompt = await asyncio.to_thread(
                        self.session_prompt.prompt,
                        f"prompt[{session.session_id}]> "
                    )
                    
                    # Check for ESC key
                    if user_prompt == '__ESC__':
                        self.console.print("\n[yellow]⚠️  ESC pressed: Stopping current operation...[/yellow]")
                        # Stop the current session operation
                        if current_task and not current_task.done():
                            current_task.cancel()
                            try:
                                await current_task
                            except asyncio.CancelledError:
                                pass
                        await self.session_manager.stop_session(session.session_id)
                        continue
                    
                    if not user_prompt.strip():
                        continue
                    
                    # Execute the prompt in a task so we can cancel it if needed
                    current_task = asyncio.create_task(self.handle_prompt(user_prompt.strip()))
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        self.console.print("\n[yellow]⚠️  Operation cancelled[/yellow]\n")
                    finally:
                        current_task = None
                    
                except KeyboardInterrupt:
                    # Ctrl+C in prompt mode: cancel any running task and return to CLI
                    if current_task and not current_task.done():
                        self.console.print("\n[yellow]⚠️  Cancelling current operation...[/yellow]")
                        current_task.cancel()
                        try:
                            await current_task
                        except asyncio.CancelledError:
                            pass
                    self.console.print("\n[cyan]Returning to CLI mode...[/cyan]\n")
                    prompt_active = False
                    break
                except EOFError:
                    prompt_active = False
                    break
    
    async def handle_session(self, args: str):
        """Handle /session <num> command."""
        if not args or not args.isdigit():
            self.console.print("[red]Error:[/red] /session requires a session number (1-9)")
            self.console.print("[dim]Usage: /session 3[/dim]")
            return
        
        session_id = int(args)
        
        # Check if session exists
        session = self.session_manager.get_session(session_id)
        
        if not session:
            # Create sessions up to the requested ID
            self.console.print(f"[cyan]Creating session {session_id}...[/cyan]")
            try:
                # Create sessions until we reach the desired ID
                while self.session_manager._next_id <= session_id:
                    created_id = self.session_manager.create_session()
                    if created_id == session_id:
                        break
                
                # Now switch to it
                if self.session_manager.switch_session(session_id):
                    self.console.print(f"[green]✓[/green] Created and switched to session {session_id}\n")
                    self.show_session_summary()
                else:
                    self.console.print(f"[red]Error:[/red] Failed to switch to session {session_id}")
                    
            except RuntimeError as e:
                self.console.print(f"[red]Error:[/red] {e}")
                return
        else:
            # Session exists, just switch
            if self.session_manager.switch_session(session_id):
                self.console.print(f"[green]✓[/green] Switched to session {session_id}\n")
                self.show_session_summary()
            else:
                self.console.print(f"[red]Error:[/red] Could not switch to session {session_id}")
    
    async def handle_watch_session(self, args: str):
        """Handle ./watch <num> or ./watch all command."""
        if not args:
            self.console.print("[red]Error:[/red] ./watch requires a session number or 'all'")
            self.console.print("[dim]Usage: ./watch 3  or  ./watch all[/dim]")
            return
        
        if args.lower() == 'all':
            await self.handle_watch_all()
        elif args.isdigit():
            session_id = int(args)
            await self.handle_watch_single(session_id)
        else:
            self.console.print("[red]Error:[/red] Invalid argument for ./watch")
            self.console.print("[dim]Usage: ./watch 3  or  ./watch all[/dim]")
    
    async def handle_watch_single(self, session_id: int):
        """Watch a single session's output."""
        session = self.session_manager.get_session(session_id)
        if not session:
            self.console.print(f"[red]Error:[/red] Session {session_id} not found")
            return
        
        self.console.print(f"\n[cyan]Watching session {session_id}... Press Ctrl+C to stop[/cyan]\n")
        
        try:
            with Live(console=self.console, refresh_per_second=2) as live:
                for _ in range(20):  # Watch for 10 seconds
                    layout = self._create_session_watch_layout(session)
                    live.update(layout)
                    await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped watching[/yellow]\n")
    
    def _create_session_watch_layout(self, session: SessionInfo) -> Layout:
        """Create layout for watching a session."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="logs", size=15),
        )
        
        # Header with status
        status_table = Table.grid(padding=(0, 2))
        status_table.add_column(style="cyan", width=15)
        status_table.add_column(style="yellow")
        
        status_table.add_row("Session ID", str(session.session_id))
        status_table.add_row("Status", session.status.value)
        status_table.add_row("Completed Tasks", str(session.completed_tasks))
        if session.goal:
            status_table.add_row("Current Goal", session.goal[:60] + "..." if len(session.goal) > 60 else session.goal)
        
        layout["header"].update(Panel(status_table, title="[bold cyan]Session Info[/bold cyan]", border_style="cyan"))
        
        # Logs
        log_text = Text()
        
        recent_logs = []
        for log in session.gpt_logs[-3:]:
            recent_logs.append(("GPT", log, "cyan"))
        for log in session.playwright_logs[-3:]:
            recent_logs.append(("Playwright", log, "blue"))
        for log in session.action_logs[-3:]:
            recent_logs.append(("Action", log, "green"))
        
        for source, log, color in recent_logs[-10:]:
            log_text.append(f"[{source:10}] ", style=f"{color} bold")
            log_text.append(f"{log}\n", style=color)
        
        if not recent_logs:
            log_text.append("No activity yet...", style="dim")
        
        layout["logs"].update(Panel(log_text, title="[bold yellow]Recent Activity[/bold yellow]", border_style="yellow"))
        
        return layout
    
    async def handle_watch_all(self):
        """Watch all sessions overview."""
        self.console.print(f"\n[cyan]Watching all sessions... Press Ctrl+C to stop[/cyan]\n")
        
        try:
            with Live(console=self.console, refresh_per_second=1) as live:
                for _ in range(30):  # Watch for 30 seconds
                    table = self._create_all_sessions_table()
                    live.update(Panel(table, title=f"[bold cyan]All Sessions - {datetime.now().strftime('%H:%M:%S')}[/bold cyan]", border_style="cyan"))
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped watching[/yellow]\n")
    
    def _create_all_sessions_table(self) -> Table:
        """Create table showing all sessions."""
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Status", width=12)
        table.add_column("Tasks", justify="right", width=6)
        table.add_column("Activity", width=15)
        table.add_column("Goal", width=40)
        
        sessions = self.session_manager.list_sessions()
        for session in sessions:
            status_color = self._get_session_color(session)
            
            # Calculate time since last activity
            if session.last_activity:
                delta = (datetime.now() - session.last_activity).total_seconds()
                if delta < 60:
                    activity = f"{int(delta)}s ago"
                else:
                    activity = f"{int(delta/60)}m ago"
            else:
                activity = "-"
            
            goal_display = (session.goal[:37] + "...") if session.goal and len(session.goal) > 40 else (session.goal or "-")
            
            table.add_row(
                str(session.session_id),
                f"[{status_color}]{session.status.value}[/{status_color}]",
                str(session.completed_tasks),
                activity,
                goal_display
            )
        
        return table
    
    async def handle_logs(self, args: str):
        """Handle ./logs command."""
        session = self.session_manager.get_active_session()
        if not session:
            self.console.print("[yellow]No active session[/yellow]")
            return
        
        log_type = args.strip().lower() if args else 'all'
        
        self.console.print()
        self.console.print(f"[bold cyan]Session {session.session_id} Logs[/bold cyan]")
        self.console.print()
        
        if log_type in ['all', 'gpt']:
            self.console.print("[bold cyan]GPT Logs:[/bold cyan]")
            if session.gpt_logs:
                for log in session.gpt_logs:
                    self.console.print(f"[cyan]{log}[/cyan]")
            else:
                self.console.print("[dim]  No GPT logs[/dim]")
            self.console.print()
        
        if log_type in ['all', 'server']:
            self.console.print("[bold magenta]Server Logs:[/bold magenta]")
            if session.server_logs:
                for log in session.server_logs:
                    self.console.print(f"[magenta]{log}[/magenta]")
            else:
                self.console.print("[dim]  No server logs[/dim]")
            self.console.print()
        
        if log_type in ['all', 'playwright']:
            self.console.print("[bold blue]Playwright Logs:[/bold blue]")
            if session.playwright_logs:
                for log in session.playwright_logs:
                    self.console.print(f"[blue]{log}[/blue]")
            else:
                self.console.print("[dim]  No Playwright logs[/dim]")
            self.console.print()
        
        if log_type in ['all', 'actions']:
            self.console.print("[bold green]Action Logs:[/bold green]")
            if session.action_logs:
                for log in session.action_logs:
                    self.console.print(f"[green]{log}[/green]")
            else:
                self.console.print("[dim]  No action logs[/dim]")
            self.console.print()
    
    async def handle_models(self):
        """Handle ./models command."""
        self.console.print()
        self.console.print("[bold cyan]Available Models[/bold cyan]")
        self.console.print()
        
        models_table = Table(show_header=True, header_style="bold magenta")
        models_table.add_column("Model", style="cyan", width=30)
        models_table.add_column("Description", style="white", width=50)
        models_table.add_column("Status", style="green", width=10)
        
        # Simulated models (would be fetched from server)
        models = [
            ("gpt-4o", "GPT-4 Optimized - Latest and most capable", "Active"),
            ("gpt-4-turbo", "GPT-4 Turbo - Fast and efficient", "Active"),
            ("gpt-4", "GPT-4 - Original release", "Active"),
            ("gpt-3.5-turbo", "GPT-3.5 Turbo - Fast and economical", "Active"),
        ]
        
        for model, desc, status in models:
            models_table.add_row(model, desc, status)
        
        self.console.print(models_table)
        self.console.print()
        self.console.print(f"[dim]Current model: {self.current_context['model']}[/dim]")
        self.console.print()
    
    async def handle_stop(self, args: str):
        """Handle /stop command."""
        if not args:
            self.console.print("[red]Error:[/red] /stop requires a session number or 'all'")
            self.console.print("[dim]Usage: /stop 3  or  /stop all[/dim]")
            return
        
        if args.lower() == 'all':
            # Stop/remove all sessions
            sessions = self.session_manager.list_sessions()
            count = 0
            for session in sessions:
                if await self.session_manager.cancel_session(session.session_id):
                    count += 1
                elif self.session_manager.remove_session(session.session_id):
                    count += 1
            
            if count > 0:
                self.console.print(f"[green]✓[/green] Stopped/removed {count} session(s)")
                # Create a new session if all were removed
                if not self.session_manager.list_sessions():
                    self.session_manager.create_session()
                    self.console.print("[cyan]Created new session 1[/cyan]")
                self.show_session_summary()
            else:
                self.console.print("[yellow]ℹ️  No sessions to stop[/yellow]")
                
        elif args.isdigit():
            # Stop specific session
            session_id = int(args)
            session = self.session_manager.get_session(session_id)
            
            if not session:
                self.console.print(f"[yellow]⚠️  Session {session_id} not found[/yellow]")
                return
            
            # Check if session has a running task
            if session.status in [SessionStatus.PLANNING, SessionStatus.EXECUTING]:
                if await self.session_manager.cancel_session(session_id):
                    self.console.print(f"[green]✓[/green] Cancelled session {session_id}")
                else:
                    self.console.print(f"[yellow]⚠️  Could not cancel session {session_id}[/yellow]")
            else:
                # Session is idle/completed/failed - just remove it
                if self.session_manager.remove_session(session_id):
                    self.console.print(f"[green]✓[/green] Removed session {session_id}")
                    # If we removed the last session, create a new one
                    if not self.session_manager.list_sessions():
                        self.session_manager.create_session()
                        self.console.print("[cyan]Created new session 1[/cyan]")
                    self.show_session_summary()
                else:
                    self.console.print(f"[yellow]⚠️  Could not remove session {session_id}[/yellow]")
        else:
            self.console.print("[red]Error:[/red] Invalid argument for /stop")
            self.console.print("[dim]Usage: /stop 3  or  /stop all[/dim]")
    
    async def handle_background(self):
        """Handle /background command."""
        self.console.print("\n[cyan]📦 Backgrounding Calico...[/cyan]")
        self.console.print("[dim]Sessions will continue running in the background[/dim]")
        self.console.print("[dim]Use 'fg' to bring Calico back to foreground[/dim]\n")
        
        # Send SIGSTOP to self
        import os
        os.kill(os.getpid(), signal.SIGSTOP)
    
    async def handle_status(self):
        """Handle /status command with session information."""
        sessions = self.session_manager.list_sessions()
        active_sessions = self.session_manager.get_active_sessions()
        
        self.console.print()
        status_table = Table(
            title="Calico Status",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan"
        )
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="yellow", justify="right")
        
        total_tasks = sum(s.completed_tasks for s in sessions)
        
        status_table.add_row("Total Sessions", str(len(sessions)))
        status_table.add_row("Active Sessions", str(len(active_sessions)))
        status_table.add_row("Total Completed Tasks", str(total_tasks))
        status_table.add_row(
            "Current Session", 
            str(self.session_manager.active_session_id) if self.session_manager.active_session_id else "None"
        )
        
        self.console.print(status_table)
        self.console.print()
        
        if sessions:
            self.show_session_summary()
    
    async def handle_efficiency(self):
        """Handle /efficiency command - show efficiency overview."""
        sessions = self.session_manager.list_sessions()
        
        self.console.print()
        self.console.print("[bold cyan]Efficiency Overview[/bold cyan]")
        self.console.print("[dim]Press Ctrl+C to return to CLI[/dim]")
        self.console.print()
        
        try:
            with Live(console=self.console, refresh_per_second=1) as live:
                for _ in range(300):  # Run for up to 5 minutes
                    layout = self._create_efficiency_layout()
                    live.update(layout)
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            # Return to CLI when Ctrl+C is pressed
            self.console.print("\n[cyan]Returning to CLI...[/cyan]\n")
            return
    
    def _create_efficiency_layout(self) -> Layout:
        """Create layout for efficiency overview."""
        layout = Layout()
        layout.split_column(
            Layout(name="summary", size=8),
            Layout(name="sessions", size=15),
        )
        
        # Summary metrics
        sessions = self.session_manager.list_sessions()
        total_tasks = sum(s.completed_tasks for s in sessions)
        active_count = len(self.session_manager.get_active_sessions())
        completed_count = len([s for s in sessions if s.status == SessionStatus.COMPLETED])
        failed_count = len([s for s in sessions if s.status == SessionStatus.FAILED])
        
        # Calculate average response time (simulated)
        avg_response = 2.3  # Would be calculated from actual data
        success_rate = (completed_count / len(sessions) * 100) if sessions else 0
        
        summary_table = Table.grid(padding=(0, 2))
        summary_table.add_column(style="cyan", width=25)
        summary_table.add_column(style="yellow", justify="right")
        
        summary_table.add_row("Total Sessions", str(len(sessions)))
        summary_table.add_row("Active Sessions", f"[green]{active_count}[/green]")
        summary_table.add_row("Completed Tasks", f"[green]{total_tasks}[/green]")
        summary_table.add_row("Success Rate", f"[green]{success_rate:.1f}%[/green]")
        summary_table.add_row("Failed Sessions", f"[red]{failed_count}[/red]")
        summary_table.add_row("Avg Response Time", f"{avg_response:.2f}s")
        
        layout["summary"].update(Panel(summary_table, title="[bold magenta]Performance Metrics[/bold magenta]", border_style="magenta"))
        
        # Sessions table with rates
        sessions_table = Table(show_header=True, header_style="bold cyan")
        sessions_table.add_column("ID", style="cyan", width=4)
        sessions_table.add_column("Status", width=12)
        sessions_table.add_column("Tasks", justify="right", width=6)
        sessions_table.add_column("Rate", justify="right", width=10)
        sessions_table.add_column("Duration", justify="right", width=10)
        
        for session in sessions:
            status_color = self._get_session_color(session)
            
            # Calculate task rate
            if session.started_at:
                if session.completed_at:
                    duration = (session.completed_at - session.started_at).total_seconds()
                else:
                    duration = (datetime.now() - session.started_at).total_seconds()
                
                rate = (session.completed_tasks / duration * 60) if duration > 0 else 0
                duration_str = f"{duration:.1f}s"
                rate_str = f"{rate:.1f}/min"
            else:
                rate_str = "-"
                duration_str = "-"
            
            sessions_table.add_row(
                str(session.session_id),
                f"[{status_color}]{session.status.value}[/{status_color}]",
                str(session.completed_tasks),
                rate_str,
                duration_str
            )
        
        layout["sessions"].update(Panel(sessions_table, title="[bold yellow]Session Efficiency[/bold yellow]", border_style="yellow"))
        
        return layout
    
    async def handle_config(self, args: str):
        """Handle /config command."""
        if not args:
            # Show config
            self.console.print()
            config_table = Table(title="Configuration", border_style="blue")
            config_table.add_column("Setting", style="cyan")
            config_table.add_column("Value", style="yellow")
            
            config_table.add_row("Model", self.current_context['model'])
            config_table.add_row("Temperature", str(self.current_context['temperature']))
            config_table.add_row("Max Sessions", str(self.session_manager.max_sessions))
            
            self.console.print(config_table)
            self.console.print()
        else:
            # Handle config set
            parts = args.split(maxsplit=2)
            if len(parts) >= 3 and parts[0] == 'set':
                key, value = parts[1], parts[2]
                self.console.print(f"[green]✓[/green] Set {key} = {value}")
                
                # Update context if relevant
                if key == 'model':
                    self.current_context['model'] = value
                elif key == 'temperature':
                    self.current_context['temperature'] = float(value)
            else:
                self.console.print("[red]Usage:[/red] /config set <key> <value>")
    
    async def run(self):
        """Run the interactive CLI."""
        self.show_welcome()
        
        while self.running:
            try:
                # Get current session for prompt
                session = self.session_manager.get_active_session()
                prompt_text = f"calico[{session.session_id if session else '?'}]> "
                
                # Get user input
                user_input = await asyncio.to_thread(
                    self.session_prompt.prompt,
                    prompt_text,
                )
                
                # Check for ESC key in CLI mode
                if user_input == '__ESC__':
                    self.console.print("[dim]ESC pressed (no operation to stop)[/dim]")
                    continue
                
                # Handle the command
                await self.handle_command(user_input)
                
            except KeyboardInterrupt:
                # Ctrl+C in CLI mode: End all sessions and exit
                self.console.print("\n[yellow]⚠️  Ctrl+C detected: Ending all sessions...[/yellow]")
                
                active = self.session_manager.get_active_sessions()
                if active:
                    count = await self.session_manager.cancel_all_sessions()
                    self.console.print(f"[green]✓[/green] Ended {count} session(s)")
                
                self.console.print("[yellow]Exiting Calico...[/yellow]")
                self.running = False
                self.console.print("[yellow]Goodbye! 👋[/yellow]")
            
            except EOFError:
                # Ctrl+D
                self.running = False
                self.console.print("\n[yellow]Goodbye! 👋[/yellow]")
            
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
                logger.error(f"Error in main loop: {e}", exc_info=True)


async def start_interactive_shell():
    """Start the interactive Calico CLI."""
    shell = CalicoShell()
    
    try:
        await shell.run()
    finally:
        # Cleanup: cancel any remaining sessions
        active = shell.session_manager.get_active_sessions()
        if active:
            console.print(f"\n[yellow]Cleaning up {len(active)} active session(s)...[/yellow]")
            await shell.session_manager.cancel_all_sessions()

