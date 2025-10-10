"""Configuration management commands."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


@click.group(name="config")
def config_command():
    """
    Manage Calico GPT configuration.
    
    Configure API keys, models, and default settings.
    """
    pass


@config_command.command(name="show")
def show_config():
    """Show current configuration."""
    config = _load_config()
    
    console.print(Panel(
        "[bold cyan]Current Configuration[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # GPT Settings
    gpt_table = Table(title="GPT Settings", border_style="blue")
    gpt_table.add_column("Setting", style="cyan")
    gpt_table.add_column("Value", style="yellow")
    
    gpt_table.add_row("API Key", _mask_key(config.get("openai_api_key", "")))
    gpt_table.add_row("Default Model", config.get("gpt_model", "gpt-4o"))
    gpt_table.add_row("Temperature", str(config.get("temperature", 0.2)))
    gpt_table.add_row("Max Tokens", str(config.get("max_tokens", 4000)))
    
    console.print(gpt_table)
    console.print()
    
    # Automation Settings
    auto_table = Table(title="Automation Settings", border_style="green")
    auto_table.add_column("Setting", style="cyan")
    auto_table.add_column("Value", style="yellow")
    
    auto_table.add_row("Max Turns", str(config.get("max_turns", 8)))
    auto_table.add_row("Timeout", f"{config.get('timeout', 10)}s")
    auto_table.add_row("Headless Mode", str(config.get("headless", True)))
    auto_table.add_row("Max Retries", str(config.get("max_retries", 3)))
    
    console.print(auto_table)
    console.print()
    
    # Monitoring Settings
    mon_table = Table(title="Monitoring Settings", border_style="magenta")
    mon_table.add_column("Setting", style="cyan")
    mon_table.add_column("Value", style="yellow")
    
    mon_table.add_row("Enable Telemetry", str(config.get("enable_telemetry", True)))
    mon_table.add_row("Log Level", config.get("log_level", "INFO"))
    mon_table.add_row("Save Screenshots", str(config.get("save_screenshots", True)))
    
    console.print(mon_table)


@config_command.command(name="set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str):
    """Set a configuration value."""
    config = _load_config()
    
    # Parse value based on key
    parsed_value = _parse_value(key, value)
    
    config[key] = parsed_value
    _save_config(config)
    
    console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [yellow]{parsed_value}[/yellow]")


@config_command.command(name="get")
@click.argument("key")
def get_config(key: str):
    """Get a configuration value."""
    config = _load_config()
    
    if key in config:
        value = config[key]
        if "key" in key.lower() or "secret" in key.lower():
            value = _mask_key(str(value))
        console.print(f"[cyan]{key}[/cyan] = [yellow]{value}[/yellow]")
    else:
        console.print(f"[red]Error:[/red] Key '[cyan]{key}[/cyan]' not found in configuration")


@config_command.command(name="init")
def init_config():
    """Initialize configuration interactively."""
    console.print(Panel(
        "[bold cyan]Initialize Calico GPT Configuration[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    config = {}
    
    # API Key
    api_key = Prompt.ask(
        "[cyan]OpenAI API Key[/cyan]",
        password=True
    )
    config["openai_api_key"] = api_key
    
    # Model
    model = Prompt.ask(
        "[cyan]Default GPT Model[/cyan]",
        default="gpt-4o",
        choices=["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
    )
    config["gpt_model"] = model
    
    # Temperature
    temperature = Prompt.ask(
        "[cyan]Temperature (0.0-2.0)[/cyan]",
        default="0.2"
    )
    config["temperature"] = float(temperature)
    
    # Max turns
    max_turns = Prompt.ask(
        "[cyan]Max Automation Turns[/cyan]",
        default="8"
    )
    config["max_turns"] = int(max_turns)
    
    # Headless mode
    headless = Confirm.ask(
        "[cyan]Run browser in headless mode?[/cyan]",
        default=True
    )
    config["headless"] = headless
    
    # Save configuration
    _save_config(config)
    
    console.print()
    console.print("[green]✓[/green] Configuration saved successfully!")
    console.print()
    console.print("[dim]Configuration file:[/dim]")
    console.print(f"[dim]{_get_config_path()}[/dim]")


@config_command.command(name="reset")
def reset_config():
    """Reset configuration to defaults."""
    if Confirm.ask("[yellow]Are you sure you want to reset all configuration?[/yellow]"):
        config = _get_default_config()
        _save_config(config)
        console.print("[green]✓[/green] Configuration reset to defaults")
    else:
        console.print("[yellow]Cancelled[/yellow]")


def _get_config_path() -> Path:
    """Get the configuration file path."""
    config_dir = Path.home() / ".calico"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.json"


def _load_config() -> dict:
    """Load configuration from file."""
    config_path = _get_config_path()
    
    if config_path.exists():
        import json
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            pass
    
    # Also check environment variables
    env_config = {}
    if os.environ.get("OPENAI_API_KEY"):
        env_config["openai_api_key"] = os.environ["OPENAI_API_KEY"]
    
    return {**_get_default_config(), **env_config}


def _save_config(config: dict):
    """Save configuration to file."""
    import json
    config_path = _get_config_path()
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def _get_default_config() -> dict:
    """Get default configuration."""
    return {
        "gpt_model": "gpt-4o",
        "temperature": 0.2,
        "max_tokens": 4000,
        "max_turns": 8,
        "timeout": 10,
        "headless": True,
        "max_retries": 3,
        "enable_telemetry": True,
        "log_level": "INFO",
        "save_screenshots": True
    }


def _parse_value(key: str, value: str):
    """Parse value based on key type."""
    # Boolean values
    if key in ["headless", "enable_telemetry", "save_screenshots"]:
        return value.lower() in ["true", "1", "yes", "y"]
    
    # Integer values
    if key in ["max_turns", "timeout", "max_retries", "max_tokens"]:
        return int(value)
    
    # Float values
    if key in ["temperature"]:
        return float(value)
    
    # String values
    return value


def _mask_key(key: str) -> str:
    """Mask API key for display."""
    if not key:
        return "[dim]Not set[/dim]"
    
    if len(key) <= 8:
        return "****"
    
    return f"{key[:4]}...{key[-4:]}"
