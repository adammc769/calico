"""Simple command-line helpers for workflow orchestration."""
from __future__ import annotations

import argparse
import json
import sys

from celery.result import AsyncResult

from .tasks import enqueue_dom_unit_collection
from .db import init_db


def cmd_init_db(args):
    """Initialize the database."""
    print("Initializing database...")
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as exc:
        print(f"❌ Database initialization failed: {exc}")
        sys.exit(1)


def cmd_serve_api(args):
    """Start the API server for Chrome extension communication."""
    try:
        from .api_server import run_server
        
        print(f"Starting API server on {args.host}:{args.port}")
        if args.reload:
            print("Auto-reload enabled for development")
            
        run_server(host=args.host, port=args.port, reload=args.reload)
        
    except ImportError:
        print("Error: FastAPI not installed. Run: pip install fastapi uvicorn[standard]")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Error starting API server: {exc}")
        sys.exit(1)


def cmd_scrape(args):
    """Schedule DOM unit collection task."""
    result: AsyncResult = enqueue_dom_unit_collection(url=args.url, limit=args.limit)
    output = {
        "task_id": result.id,
        "state": result.state,
    }
    print(json.dumps(output, indent=2))


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Calico workflow management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Database initialization command
    init_parser = subparsers.add_parser("init-db", help="Initialize the database")
    init_parser.set_defaults(func=cmd_init_db)
    
    # API server command
    api_parser = subparsers.add_parser("serve-api", help="Start the API server for Chrome extension")
    api_parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    api_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    api_parser.set_defaults(func=cmd_serve_api)
    
    # Legacy scraping command
    scrape_parser = subparsers.add_parser("scrape", help="Schedule DOM unit collection task")
    scrape_parser.add_argument("url", help="URL to scrape for DOM units")
    scrape_parser.add_argument("--limit", type=int, default=None, help="Maximum number of units to capture")
    scrape_parser.set_defaults(func=cmd_scrape)
    
    # Parse arguments and execute
    args = parser.parse_args(argv)
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return
        
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
