# Calico ![calico svg](calico.svg)

**Context-Aware Learning and Intelligent Command Orchestrator**

AI-powered browser automation with GPT reasoning, visual intelligence, and distributed architecture.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Playwright](https://img.shields.io/badge/playwright-1.55.0-green.svg)](https://playwright.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange.svg)](https://openai.com/)

**Tags:** `ai-automation` `browser-automation` `gpt-4` `playwright` `web-scraping` `ocr` `intelligent-agents` `python` `celery` `redis`

## Quick Start

```bash
# Install dependencies
pip install -r requirements/base.requirements.txt

# Set API key
export OPENAI_API_KEY=sk-your-key

# Launch interactive shell
./bin/calico
```

## Features

- **AI-Powered**: GPT-4 integration for intelligent task planning and execution
- **Visual Intelligence**: OCR support for CAPTCHAs, images, and complex layouts using Tesseract and Google Cloud Vision
- **Interactive CLI**: Active shell with tab completion and real-time monitoring
- **Anti-Detection**: Enhanced browser fingerprinting evasion using Patchright
- **Session Management**: Organized storage for screenshots, logs, and training data
- **Distributed Architecture**: Scalable design with Celery workers and Redis for session isolation
- **MCP Integration**: Browser control via Model Context Protocol (MCP) WebSocket service

## Configuration

### Browser Control Options

Calico supports two browser control methods:

1. **Python Server** (default): Direct Playwright integration with built-in stealth features
2. **MCP Server** (alternative): Model Context Protocol WebSocket service for remote browser control

Key environment variables:

```bash
# AI Services
OPENAI_API_KEY=sk-...                    # Required: GPT-4 API key
GOOGLE_APPLICATION_CREDENTIALS=./keys/   # Optional: Google Vision OCR

# Browser Automation (Python Server - default)
PLAYWRIGHT_HEADLESS=true                # Browser display mode

# Browser Automation (MCP Server - alternative)
MCP_WS_URL=ws://localhost:7001          # MCP WebSocket service URL

# Session Storage
SESSION_STORAGE_DIR=./sessions          # Base directory for session data
```

Session storage structure:
```
./sessions/{session-uuid}/
├── metadata.json
├── photos/
├── logs/
└── data/
```

## Architecture

- **Calico Core**: Main automation engine with GPT-4 reasoning
- **Browser Layer**: Playwright/Patchright for stealth automation (default: Python server, alternative: MCP WebSocket server)
- **Vision Layer**: Multi-provider OCR (Tesseract, Google Cloud Vision)
- **Task Queue**: Celery with Redis for distributed processing
- **Session Storage**: UUID-based isolation for screenshots, logs, and data

## License

MIT License - see [LICENSE](LICENSE) file for details.