from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol

from .actions import AIAction

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency resolution
    from openai import AsyncOpenAI, OpenAI
except Exception:  # pragma: no cover - guard for environments without openai installed
    AsyncOpenAI = None  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]


def analyze_page_for_intelligence(page_context: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Phase 1 Critical Integration: Form Intelligence Analysis
    
    Integrates form_components.py and fuzzy_forms.py to provide semantic understanding
    of page elements and intelligent selector strategies to the AI model.
    """
    try:
        url = page_context.get("url", "")
        
        # Determine page type for fallback strategies
        page_type = "unknown"
        if "google" in url.lower():
            if "images" in url.lower():
                page_type = "google_images_search"
            else:
                page_type = "google_search"
        elif "login" in url.lower() or "signin" in url.lower():
            page_type = "login_page"
        elif "search" in url.lower():
            page_type = "search_page"
            
        # Enhanced intelligence for known page types
        intelligence = {
            "page_type": page_type,
            "form_elements": [],
            "interaction_strategies": _get_fallback_strategies(page_type),
            "recommended_selectors": _get_fallback_selectors(page_type),
            "confidence_analysis": {
                "mode": "fallback_intelligence", 
                "page_type_confidence": 85 if page_type != "unknown" else 30
            }
        }
        
        logger.info("Generated page intelligence (Phase 1)", extra={
            "page_type": page_type,
            "strategies_count": len(intelligence["interaction_strategies"]),
            "selector_sets": len(intelligence["recommended_selectors"])
        })
        
        return intelligence
        
    except Exception as e:
        logger.warning("Page intelligence analysis failed, using minimal fallback", exc_info=e)
        return {
            "page_type": "unknown",
            "form_elements": [],
            "interaction_strategies": [],
            "recommended_selectors": {},
            "confidence_analysis": {"mode": "minimal_fallback", "error": str(e)}
        }


def _get_fallback_strategies(page_type: str) -> list:
    """Phase 1: Fallback strategies for known page types"""
    strategies = {
        "google_search": [
            {
                "type": "search_interaction",
                "strategy": "Use enhanced Google search selectors with multiple fallbacks",
                "priority": "critical",
                "approach": "multi_selector_fallback"
            }
        ],
        "google_images_search": [
            {
                "type": "search_interaction", 
                "strategy": "Use Google Images specific selectors with aggressive fallbacks",
                "priority": "critical",
                "approach": "enhanced_selector_cascade",
                "note": "Google Images may have different DOM structure than main search"
            }
        ],
        "search_page": [
            {
                "type": "search_interaction",
                "strategy": "Use generic search patterns with common fallbacks",
                "priority": "high"
            }
        ],
        "login_page": [
            {
                "type": "authentication",
                "strategy": "Use semantic field detection for login forms",
                "priority": "high"
            }
        ]
    }
    
    return strategies.get(page_type, [{
        "type": "generic_interaction",
        "strategy": "Use conservative selector patterns with timeouts",
        "priority": "medium"
    }])


def _get_fallback_selectors(page_type: str) -> Dict[str, str]:
    """Phase 1: Enhanced selectors for known page types - solves Google Images issue"""
    selectors = {
        "google_search": {
            "search_input": 'input[name="q"], input[type="search"], input[aria-label*="search" i], textarea[name="q"], #search-input, [role="searchbox"]',
            "search_button": 'button[type="submit"], input[type="submit"], button[aria-label*="search" i], [role="button"][aria-label*="search"]',
            "search_results": 'div[data-ved], div.g, .tF2Cxc, [data-result-index], .kvH3mc, .MjjYud, .hlcw0c, div[jscontroller][lang], .yuRUbf, div.kvH3mc div.Z26q7c, div[data-async-context], .ULSxyf'
        },
        "google_images_search": {
            "search_input": 'input[name="q"], textarea[name="q"], input[type="search"], input[aria-label*="search" i], #search-input, [role="searchbox"], input[placeholder*="search" i]',
            "search_button": 'button[type="submit"], input[type="submit"], button[aria-label*="search" i], [role="button"]:has-text("Search")',
            "search_results": 'div[data-ved], .rg_i, .isv-r, div[jsname], [data-result-index], .mNsIhb, div[data-ri], .bRMDJf, .islir, div[data-async-context]'
        },
        "search_page": {
            "search_input": 'input[type="search"], input[name*="search"], input[placeholder*="search" i], input[aria-label*="search" i]',
            "search_button": 'button[type="submit"], input[type="submit"], button:has-text("Search")'
        },
        "login_page": {
            "email_input": 'input[type="email"], input[name="email"], input[placeholder*="email" i]',
            "password_input": 'input[type="password"], input[name="password"], input[placeholder*="password" i]',
            "submit_button": 'button[type="submit"], input[type="submit"], button:has-text("Sign in"), button:has-text("Login")'
        }
    }
    
    return selectors.get(page_type, {
        "primary_input": 'input[type="text"], textarea, input:not([type="hidden"])',
        "primary_button": 'button, input[type="submit"], [role="button"]'
    })


@dataclass(slots=True)
class LLMPlan:
    """Structured response from an LLM call."""

    actions: list[AIAction] = field(default_factory=list)
    reasoning: str = ""
    done: bool = False
    recovery_actions: list[AIAction] = field(default_factory=list)
    raw: Optional[str] = None


class LLMClient(Protocol):
    """Protocol describing the behaviour expected from any LLM backend."""

    async def plan_actions(
        self,
        *,
        goal: str,
        context: Mapping[str, Any] | None,
        state: Mapping[str, Any],
        error: str | None = None,
    ) -> LLMPlan:
        ...


class OpenAILLMClient:
    """Minimal async wrapper around OpenAI's Responses or Chat Completions APIs."""

    def __init__(
        self,
        *,
        model: str,
        client: Any | None = None,
        temperature: float = 0.2,
        system_prompt: str | None = None,
    ) -> None:
        if client is None:
            if AsyncOpenAI is not None:
                client = AsyncOpenAI()
            elif OpenAI is not None:
                client = OpenAI()
            else:  # pragma: no cover - dependency guard
                raise ImportError("The openai package is required to use OpenAILLMClient")

        self._client = client
        self._model = model
        self._temperature = temperature
        self._system_prompt = system_prompt or self._default_system_prompt()

    async def plan_actions(
        self,
        *,
        goal: str,
        context: Mapping[str, Any] | None,
        state: Mapping[str, Any],
        error: str | None = None,
        page_analysis: Mapping[str, Any] | None = None,  # Phase 1 
        context_enhancer: Optional[Any] = None,  # Phase 2: Full context enhancement
        session_id: Optional[str] = None,  # Phase 2: For MCP integration
    ) -> LLMPlan:
        
        # Check for candidate-based flow first (token-efficient)
        if context and context.get("use_candidate_flow", False):
            logger.info("Using candidate-based flow for token efficiency")
            return await self._plan_with_candidates(goal, context, state, error)
        
        # === PHASE 2: FULL CONTEXT ENHANCEMENT ===
        if context_enhancer:
            try:
                logger.info("Using Phase 2: Full context enhancement")
                enhanced_intelligence = await context_enhancer.enhance_context(
                    goal=goal,
                    basic_context=context or {},
                    session_state=state,
                    session_id=session_id
                )
                
                # Convert PageIntelligence to dict for JSON serialization
                payload = {
                    "goal": goal,
                    "context": context or {},
                    "state": state,
                    "comprehensive_intelligence": {
                        "page_type": enhanced_intelligence.page_type,
                        "confidence": enhanced_intelligence.confidence,
                        "form_elements": enhanced_intelligence.form_elements,
                        "page_content": enhanced_intelligence.page_content,
                        "dom_structure": enhanced_intelligence.dom_structure,
                        "visual_context": enhanced_intelligence.visual_context,
                        "interaction_strategies": enhanced_intelligence.interaction_strategies,
                        "recommended_selectors": enhanced_intelligence.recommended_selectors,
                        "performance_insights": enhanced_intelligence.performance_insights,
                        "analysis_timestamp": enhanced_intelligence.timestamp
                    }
                }
                
                logger.info("Phase 2 context enhancement complete", extra={
                    "page_type": enhanced_intelligence.page_type,
                    "confidence": enhanced_intelligence.confidence,
                    "data_sources": len([k for k, v in enhanced_intelligence.telemetry_data.get("data_sources", {}).items() if v])
                })
                
            except Exception as e:
                logger.error("Phase 2 context enhancement failed, falling back to Phase 1", exc_info=e)
                # Fallback to Phase 1 or basic context
                payload = self._create_fallback_payload(goal, context, state, page_analysis)
        
        # === PHASE 1: FORM INTELLIGENCE (Fallback) ===  
        elif page_analysis:
            payload = {
                "goal": goal,
                "context": context or {},
                "state": state,
                "page_intelligence": page_analysis
            }
            logger.debug("Using Phase 1: Form intelligence context")
            
        # === BASIC CONTEXT (Original) ===
        else:
            payload = {
                "goal": goal,
                "context": context or {},
                "state": state,
            }
            logger.debug("Using basic context (no enhancement)")
            
        if error:
            payload["last_error"] = error

        prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        logger.debug("Submitting plan request to OpenAI", extra={"model": self._model, "enhancement_level": "Phase2" if context_enhancer else "Phase1" if page_analysis else "Basic"})

        response_text = await self._invoke_model(prompt)
        return self._parse_response_text(response_text)
    
    async def _plan_with_candidates(
        self, 
        goal: str, 
        context: Mapping[str, Any], 
        state: Mapping[str, Any], 
        error: Optional[str]
    ) -> LLMPlan:
        """Token-efficient planning using only top candidates and OCR chunks."""
        
        # Extract only essential data
        candidates = context.get("candidates", [])[:10]  # Top 10 candidates only
        ocr_chunks = context.get("ocr_chunks", [])[:5]   # Top 5 OCR chunks only  
        page_type = context.get("page_type", "unknown")
        url = context.get("url", "")
        
        # Create minimal payload
        payload = {
            "goal": goal,
            "page_info": {
                "url": url,
                "type": page_type,
                "turn": context.get("turn", 1)
            },
            "dom_candidates": candidates,
            "ocr_text": ocr_chunks,
            "state": {
                "turns": state.get("turns", 0),
                "last_actions": state.get("history", [])[-3:] if state.get("history") else []  # Only last 3 actions
            }
        }
        
        if error:
            payload["last_error"] = error
        
        # Enhanced selectors for known page types
        if page_type in ["google_search", "google_images_search"]:
            payload["enhanced_selectors"] = _get_fallback_selectors(page_type)
        
        prompt = json.dumps(payload, ensure_ascii=False, indent=1)  # Compact JSON
        
        # Log token efficiency
        estimated_tokens = len(prompt) // 4  # Rough estimate
        logger.info(f"Candidate-based flow: ~{estimated_tokens} tokens (vs potential 60k+)")
        
        response_text = await self._invoke_model(prompt)
        return self._parse_response_text(response_text)
    
    def _create_fallback_payload(self, goal, context, state, page_analysis):
        """Create fallback payload when Phase 2 enhancement fails"""
        payload = {
            "goal": goal,
            "context": context or {},
            "state": state,
        }
        
        if page_analysis:
            payload["page_intelligence"] = page_analysis
            
        payload["enhancement_status"] = "fallback_to_phase1"
        return payload

    async def _invoke_model(self, prompt: str) -> str:
        # Always use the chat API as it's the most reliable and widely supported
        if hasattr(self._client, "chat"):
            return await self._invoke_chat_api(prompt)
        # Fallback to responses API if available (experimental)
        if hasattr(self._client, "responses"):
            return await self._invoke_responses_api(prompt)
        raise RuntimeError("Unsupported OpenAI client configuration")

    async def _invoke_responses_api(self, prompt: str) -> str:
        request = {
            "model": self._model,
            "temperature": self._temperature,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": self._system_prompt},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        }

        create = getattr(self._client.responses, "create")
        try:
            # First try as async - most modern OpenAI clients use async
            result = create(**request)
            if inspect.iscoroutine(result):
                response = await result
            else:
                # It returned a non-coroutine, so it's sync
                response = result
        except TypeError:
            # If direct call fails, try with to_thread for sync functions
            response = await asyncio.to_thread(create, **request)

        outputs = getattr(response, "output", None) or getattr(response, "data", None)
        if not outputs:
            raise RuntimeError("OpenAI response did not contain output content")

        for item in outputs:
            content = getattr(item, "content", None)
            if not content:
                continue
            for block in content:
                if getattr(block, "type", None) == "output_text":
                    return block.text
                if getattr(block, "type", None) == "text":  # fallback
                    return block.text
        raise RuntimeError("Unable to extract text from OpenAI response")

    async def _invoke_chat_api(self, prompt: str) -> str:
        request = {
            "model": self._model,
            "temperature": self._temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

        create = getattr(self._client.chat.completions, "create")
        try:
            # First try as async - most modern OpenAI clients use async
            result = create(**request)
            if inspect.iscoroutine(result):
                response = await result
            else:
                # It returned a non-coroutine, so it's sync
                response = result
        except TypeError:
            # If direct call fails, try with to_thread for sync functions
            response = await asyncio.to_thread(create, **request)

        message = response.choices[0].message
        content = getattr(message, "content", None)
        if content is None:
            raise RuntimeError("OpenAI chat response did not include content")
        return content

    def _parse_response_text(self, text: str) -> LLMPlan:
        raw = text.strip()
        cleaned = raw
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.strip()
            lower = cleaned.lower()
            if lower.startswith("json"):
                cleaned = cleaned[4:].lstrip()
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            logger.debug("Successfully parsed LLM response JSON", extra={"data": data})
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM response as JSON", exc_info=exc, extra={"raw_response": cleaned})
            raise ValueError("LLM response was not valid JSON") from exc

        reasoning = data.get("reasoning") or data.get("analysis") or ""
        actions_payload = data.get("actions") or []
        recovery_payload = data.get("recovery_actions") or []

        # Validate and parse actions with better error handling
        actions = []
        for i, item in enumerate(actions_payload):
            try:
                if not isinstance(item, dict):
                    logger.warning(f"Action {i} is not a dictionary: {item}")
                    continue
                if "type" not in item:
                    logger.warning(f"Action {i} missing required 'type' field: {item}")
                    continue
                actions.append(AIAction.from_dict(item))
            except ValueError as e:
                logger.warning(f"Invalid action {i} in LLM response: {e}, item: {item}")
                continue

        # Validate and parse recovery actions
        recovery_actions = []
        for i, item in enumerate(recovery_payload):
            try:
                if not isinstance(item, dict):
                    logger.warning(f"Recovery action {i} is not a dictionary: {item}")
                    continue  
                if "type" not in item:
                    logger.warning(f"Recovery action {i} missing required 'type' field: {item}")
                    continue
                recovery_actions.append(AIAction.from_dict(item))
            except ValueError as e:
                logger.warning(f"Invalid recovery action {i} in LLM response: {e}, item: {item}")
                continue

        done = bool(data.get("done"))

        return LLMPlan(actions=actions, reasoning=reasoning, done=done, recovery_actions=recovery_actions, raw=raw)

    def _json_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "done": {"type": "boolean"},
                "actions": {
                    "type": "array",
                    "items": self._action_schema(),
                },
                "recovery_actions": {
                    "type": "array",
                    "items": self._action_schema(),
                },
            },
            "required": ["actions", "done"],
            "additionalProperties": True,
        }

    def _action_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["goto", "click", "fill", "press", "hover", "wait_for", "check", "uncheck", "screenshot", "delay", "extract_text", "extract", "get_text"],
                },
                "target": {"type": "string"},
                "value": {"type": ["string", "null"]},
                "metadata": {"type": "object"},
                "confidence": {"type": ["number", "null"]},
            },
            "required": ["type", "target"],
            "additionalProperties": True,
        }

    def _default_system_prompt(self) -> str:
        return (
            "You are an advanced AI reasoning engine for intelligent web automation with comprehensive page understanding. "
            "You have access to multi-modal intelligence including form analysis, visual context, DOM structure, and performance learning.\n\n"
            
            "CRITICAL OUTPUT REQUIREMENT:\n"
            "When providing answers to user queries (prices, product info, search results), YOU MUST:\n"
            "1. Parse extracted text to identify key information (product names, prices, ratings)\n"
            "2. Format information clearly and professionally in your reasoning\n"
            "3. Present prices with proper formatting: '$449.00' not '$44900' or 'current price $449.00'\n"
            "4. Structure responses with clear labels: 'Product: X | Price: $Y | Rating: Z'\n"
            "5. Remove UI noise/clutter from extracted text before presenting to user\n\n"
            
            "RESPONSE FORMAT - Always return valid JSON:\n"
            "{\n"
            '  "reasoning": "Parse and format extracted data clearly for user - this is what they see!",\n'
            '  "actions": [\n'
            '    {\n'
            '      "type": "click|fill|press|goto|hover|wait_for|check|uncheck|screenshot|delay|extract_text",\n'
            '      "target": "Enhanced multi-fallback CSS selector",\n'
            '      "value": "text to type (for fill) or key name (for press like Enter, Escape)",\n'
            '      "confidence": 0.95\n'
            '    }\n'
            '  ],\n'
            '  "done": true|false\n'
            "}\n\n"
            
            "COMPREHENSIVE INTELLIGENCE USAGE:\n"
            "- PHASE 2: If comprehensive_intelligence is provided, prioritize its insights over basic analysis\n"
            "- Use page_type and confidence scores to guide strategy selection\n"
            "- Leverage form_elements with canonical field mappings for semantic understanding\n"
            "- Apply visual_context for layout-aware interactions when available\n"
            "- Consider dom_structure for optimal interaction flow and element grouping\n"
            "- Use performance_insights to avoid known failure patterns and optimize timing\n"
            "- PHASE 1: If only page_intelligence is provided, use enhanced selector strategies\n"
            "- BASIC: If no intelligence provided, use conservative fallback patterns\n"
            
            "ENHANCED SELECTOR STRATEGY:\n"
            "- Use recommended_selectors from intelligence when available (highest priority)\n"
            "- Build multi-fallback selectors: primary + semantic + visual + aria-based\n"
            "- For search: 'input[name=\"q\"], textarea[name=\"q\"], input[type=\"search\"], [role=\"searchbox\"], input[aria-label*=\"search\" i], #search-input, input[placeholder*=\"search\" i]'\n"
            "- For buttons: 'button[type=\"submit\"], input[type=\"submit\"], button:has-text(\"Submit\"), [role=\"button\"]:has-text(\"Submit\"), button[aria-label*=\"submit\" i]'\n"
            "- For e-commerce products (Walmart): '[data-item-id], div[role=\"group\"][data-item-id]'\n"
            "  * Walmart uses data-item-id to identify individual product items\n"
            "  * Product links have link-identifier attribute  \n"
            "  * IMPORTANT: Wait for container first: '[data-testid=\"list-view\"]' then products\n"
            "  * Example sequence: wait_for('[data-testid=\"list-view\"]') then extract/click '[data-item-id]'\n"
            "- Always include 5-7 fallback selectors for critical interactions\n"
            "- Use visual_context bounding boxes to disambiguate when multiple matches exist\n"
            
            "PERFORMANCE-DRIVEN DECISION MAKING:\n"
            "- If performance_insights shows previous timeouts, use more aggressive fallback strategies\n"
            "- Apply successful patterns from performance learning\n"
            "- Adjust timing and confidence based on page complexity scores\n"
            "- Use cached insights for known page types and interaction patterns\n"
            
            "VISUAL AND SPATIAL AWARENESS:\n"
            "- When visual_context is available, consider element positioning and layout\n"
            "- Use OCR detected text to validate selector targets\n"
            "- Apply spatial relationships for interaction flow optimization\n"
            "- Consider viewport size and responsive design implications\n"
            
            "ADAPTIVE ERROR RECOVERY:\n"
            "- If last_error + performance_insights indicate pattern, adapt strategy completely\n"
            "- Use DOM structure intelligence to find alternative interaction paths\n"
            "- Apply visual confirmation when available for critical actions\n"
            "- Lower confidence and add wait strategies for historically problematic interactions\n"
            
            "INTELLIGENCE-DRIVEN RELIABILITY:\n"
            "- Each action MUST have 'type' and 'target' fields\n"
            "- Use intelligence confidence scores to guide your own confidence ratings\n"
            "- Prioritize high-confidence elements from form analysis\n"
            "- Set 'done': true only when goal is complete and confidence is high\n"
            "- Consider interaction_strategies from intelligence for optimal approach\n"
            "- Validate selector reliability using performance and visual data\n"
            
            "ACTION TYPE USAGE GUIDE:\n"
            "- screenshot: Use for capturing page state, target='full_page'|'viewport'|selector\n"
            "  Example: {'type': 'screenshot', 'target': 'full_page'}\n"
            "- delay: Use for time-based waits, target=duration (e.g. '3000', '3s', '2000ms')\n"
            "  Example: {'type': 'delay', 'target': '3000'} for 3 second wait\n"
            "- wait_for: Use for element visibility waits, target=CSS selector\n"
            "  Example: {'type': 'wait_for', 'target': 'button[type=\"submit\"]'}\n"
            "- press: Use for keyboard keys ONLY (Enter, Escape, Tab, etc.), target=input selector, value=key name\n"
            "  Example: {'type': 'press', 'target': 'input[name=\"q\"]', 'value': 'Enter'}\n"
            "  CRITICAL: Use 'press' with value='Enter' to submit forms via keyboard, NOT for clicking buttons\n"
            "  For clicking buttons, use 'click' action instead\n"
            "- click: Use for clicking buttons, links, and interactive elements, target=element selector\n"
            "  Example: {'type': 'click', 'target': 'button[type=\"submit\"]'}\n"
            "- extract_text: Extract visible text from page or element, target='body' (full page) or selector\n"
            "  Example: {'type': 'extract_text', 'target': 'body'} - extracts all page text\n"
            "  Example: {'type': 'extract_text', 'target': '.product-list'} - extracts text from specific area\n"
            "  The extracted text will be available for analysis and formatting in subsequent actions\n"
            "  Use this to gather information before presenting it to the user\n"
            "- NEVER use duration strings like '3000ms' as CSS selectors in wait_for actions\n"
            "- ALWAYS use 'delay' action for time-based waits, NOT 'wait_for'\n"
            "- ALWAYS use 'press' with value='Enter' to submit search forms, NOT 'click' on search button\n"
            
            "AUTHENTICATION PAGE HANDLING (CRITICAL - Prevents Redirect Loops):\n"
            "- When the current URL contains 'login', 'signin', 'signup', 'register', or 'auth', you are ALREADY on an authentication page\n"
            "- DO NOT navigate to another auth page if you're already on one (e.g., don't goto './auth/login' when on '/login')\n"
            "- INSTEAD: Look for credential input fields (email, username, password) on the CURRENT page\n"
            "- Use the login_page recommended selectors: input[type=\"email\"], input[type=\"password\"], etc.\n"
            "- Fill in the credentials and submit the form on the current page\n"
            "- Only navigate to an auth page if you are NOT currently on one\n"
            "- Example: If current_url='example.com/login' and goal='login', then fill credentials, don't goto './auth/login'\n"
            "- Example: If current_url='example.com/home' and goal='login', then goto 'example.com/login' first\n"
            
            "TEXT EXTRACTION AND ANALYSIS WORKFLOW:\n"
            "1. Use extract_text to gather text from page or specific elements\n"
            "2. The extracted text is stored and will be visible in the action metadata\n"
            "3. In your reasoning, analyze and format the extracted text for the user\n"
            "4. Present structured information (like lists, tables) in a clear format\n"
            "5. When the goal requires text output (e.g., 'get top 3 bikes'), extract relevant elements\n"
            "6. Analyze the extracted text and provide formatted output in your reasoning\n"
            "\n"
            "E-COMMERCE TEXT FORMATTING:\n"
            "When extracting product information (prices, titles, descriptions):\n"
            "- Parse the raw text to identify product name, price, rating, availability\n"
            "- Format prices clearly: 'Price: $449.00' not '$44900' or 'current price $449.00'\n"
            "- Present information in a structured format:\n"
            "  Product: [Name]\n"
            "  Price: $[Amount]\n"
            "  Rating: [X.X] stars ([Y] reviews)\n"
            "  Availability: [Status]\n"
            "- For multiple products, use numbered lists with clear separation\n"
            "- Extract key information and ignore navigation/UI text\n"
            "\n"
            "EXTRACTING MULTIPLE PRODUCTS:\n"
            "When asked for 'top N products' or multiple items:\n"
            "- INCORRECT: extract_text('[data-item-id]:nth-of-type(-n+5)')  ❌ Only gets 1 item\n"
            "- CORRECT: Use the parent container to get ALL products:\n"
            "  1. Extract all products at once: extract_text('[data-testid=\"list-view\"]')\n"
            "  2. The extracted text will contain multiple products\n"
            "  3. In your reasoning, parse and separate the first N products\n"
            "  4. Format each product with number, name, price, rating\n"
            "- Alternative: Extract entire search results area to get all products\n"
            "- Playwright extract_text gets ALL matching elements' text combined\n"
            "- You must parse the combined text to identify individual products\n"
            "\n"
            "PARSING MULTIPLE PRODUCTS FROM TEXT:\n"
            "Product boundaries in extracted text can be identified by:\n"
            "- Price patterns: '$XXX.XX' or 'current price $'\n"
            "- 'Add' buttons: Text often contains 'Add' between products\n"
            "- Rating patterns: 'X.X out of 5 Stars' or 'X.X stars'\n"
            "- Review counts: 'XXX reviews'\n"
            "Example: 'Product1 Add$99.994.5stars100reviewsProduct2 Add$149.994.2stars50reviews'\n"
            "Parse as 2 products by identifying the price+rating pattern repeating\n"
            "\n"
            "Example workflow for 'find price of Nintendo Switch on Walmart':\n"
            "   - Navigate to walmart.com\n"
            "   - Fill search with 'Nintendo Switch' and press Enter\n"
            "   - Wait for product container: wait_for('[data-testid=\"list-view\"]')\n"
            "   - Extract text from first product: extract_text('[data-item-id]:first')\n"
            "   - In reasoning, parse extracted text and format clearly:\n"
            "     Raw: 'Nintendo Switch 2 System100+bought$44900current price$449.004.7stars4462reviews'\n"
            "     Formatted: 'The Nintendo Switch 2 System is priced at $449.00 (4.7/5 stars from 4,462 reviews)'\n"
            "   - ALWAYS parse numbers/prices from compressed text (e.g., '$44900' becomes '$449.00')\n"
            "   - ALWAYS separate words when text is compressed (e.g., 'SystemAdd' becomes 'System')\n"
            "   - Set done=true with formatted answer\n"
            "\n"
            "Example workflow for 'find top 5 bikes on Walmart':\n"
            "   - Navigate to walmart.com\n"
            "   - Fill search with 'bikes' and press Enter\n"
            "   - Wait for product container: wait_for('[data-testid=\"list-view\"]')\n"
            "   - Extract ALL products from results area (they'll be in one text block)\n"
            "   - In reasoning, identify product boundaries (look for price patterns, 'Add' buttons, ratings)\n"
            "   - Parse and format the first 5 products:\n"
            "     1. Product: [Name]\n"
            "        Price: $[Amount]\n"
            "        Rating: [X.X]/5 stars\n"
            "     2. Product: [Name]\n"
            "        Price: $[Amount]\n"
            "        Rating: [X.X]/5 stars\n"
            "     (etc.)\n"
            "   - Set done=true with formatted list\n"

            
            "CONTEXT ADAPTATION:\n"
            "- Adapt interaction style based on detected page_type\n"
            "- Use semantic understanding from canonical field mappings\n"
            "- Apply page-specific optimizations from intelligence analysis\n"
            "- Consider content structure and DOM complexity in planning\n"
            "- Leverage telemetry data for continuous improvement"
        )
