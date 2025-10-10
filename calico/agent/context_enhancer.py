"""
Phase 2: Full Context Enhancement - Central Intelligence Coordinator

This module integrates all available utils to provide maximum intelligence
to the AI model for superior decision making and automation reliability.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PageIntelligence:
    """Comprehensive page intelligence data structure"""
    page_type: str
    confidence: float
    form_elements: List[Dict[str, Any]] = field(default_factory=list)
    page_content: Dict[str, Any] = field(default_factory=dict)
    dom_structure: Dict[str, Any] = field(default_factory=dict)
    visual_context: Dict[str, Any] = field(default_factory=dict)
    interaction_strategies: List[Dict[str, Any]] = field(default_factory=list)
    recommended_selectors: Dict[str, str] = field(default_factory=dict)
    performance_insights: Dict[str, Any] = field(default_factory=dict)
    telemetry_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ContextEnhancer:
    """
    Phase 2: Central Intelligence Coordinator
    
    Integrates all utils to provide maximum intelligence:
    - Form Intelligence (form_components.py + fuzzy_forms.py)
    - Page Content Analysis (page_text.py + dom_regions.py)  
    - DOM Structure Understanding (dom_units.py)
    - Visual Context (mcp_screenshot.py + OCR)
    - Performance Learning (mcp_telemetry.py)
    - Human-like Interactions (bot_detection/mouse.py)
    """
    
    def __init__(self, mcp_client=None, enable_visual_context: bool = True, session_storage=None):
        self.mcp_client = mcp_client
        self.enable_visual_context = enable_visual_context
        self._performance_cache = {}
        self._session_storage = session_storage
        
    async def enhance_context(
        self,
        goal: str,
        basic_context: Mapping[str, Any],
        session_state: Mapping[str, Any],
        page_reference: Optional[Any] = None,
        session_id: Optional[str] = None
    ) -> PageIntelligence:
        """
        Generate comprehensive page intelligence using all available utils.
        
        This is the central coordinator that orchestrates all intelligence gathering.
        """
        logger.info("Starting comprehensive context enhancement", extra={
            "goal": goal,
            "page_url": basic_context.get("url", "unknown"),
            "session_turn": session_state.get("turns", 0)
        })
        
        # Initialize intelligence structure
        intelligence = PageIntelligence(
            page_type="analyzing",
            confidence=0.0
        )
        
        try:
            # === PARALLEL INTELLIGENCE GATHERING ===
            tasks = []
            
            # 1. Form Intelligence Analysis
            tasks.append(self._analyze_form_intelligence(page_reference, basic_context))
            
            # 2. Page Content Analysis  
            tasks.append(self._analyze_page_content(page_reference, basic_context))
            
            # 3. DOM Structure Analysis
            tasks.append(self._analyze_dom_structure(page_reference, basic_context))
            
            # 4. Performance Analysis
            tasks.append(self._analyze_performance_context(session_state, basic_context))
            
            # 5. Visual Context (if enabled and MCP client available)
            if self.enable_visual_context and self.mcp_client and session_id:
                tasks.append(self._capture_visual_context(session_id, basic_context))
            else:
                tasks.append(asyncio.sleep(0))  # Dummy task
                
            # Execute all analyses in parallel for maximum efficiency
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # === INTELLIGENCE SYNTHESIS ===
            form_intelligence = results[0] if not isinstance(results[0], Exception) else {}
            page_content = results[1] if not isinstance(results[1], Exception) else {}
            dom_structure = results[2] if not isinstance(results[2], Exception) else {}
            performance_insights = results[3] if not isinstance(results[3], Exception) else {}
            visual_context = results[4] if not isinstance(results[4], Exception) else {}
            
            # Synthesize all intelligence into comprehensive understanding
            intelligence = self._synthesize_intelligence(
                form_intelligence,
                page_content,
                dom_structure,
                performance_insights,
                visual_context,
                goal,
                basic_context,
                session_state
            )
            
            # === TELEMETRY AND LEARNING ===
            await self._emit_intelligence_telemetry(intelligence, session_id)
            
            logger.info("Context enhancement complete", extra={
                "page_type": intelligence.page_type,
                "confidence": intelligence.confidence,
                "form_elements": len(intelligence.form_elements),
                "strategies": len(intelligence.interaction_strategies),
                "selectors": len(intelligence.recommended_selectors)
            })
            
            return intelligence
            
        except Exception as e:
            logger.error("Context enhancement failed", exc_info=e)
            # Return fallback intelligence
            return self._create_fallback_intelligence(basic_context, session_state)
    
    async def _analyze_form_intelligence(self, page_reference, context) -> Dict[str, Any]:
        """Phase 2: Enhanced form intelligence with full util integration"""
        try:
            from calico.utils.form_components import collect_form_candidates
            from calico.utils.fuzzy_forms import select_best_candidates_by_field
            
            if not page_reference:
                return self._get_fallback_form_intelligence(context)
                
            # Collect comprehensive form data
            form_candidates = collect_form_candidates(
                page_reference,
                include_fuzzy_matches=True,
                fuzzy_score_cutoff=60,  # Lower threshold for more comprehensive analysis
                fuzzy_limit=10  # More candidates for better analysis
            )
            
            # Get field rankings with disambiguation
            field_rankings = select_best_candidates_by_field(
                form_candidates,
                score_tolerance=0.1  # More sensitive to score differences
            )
            
            # Enhanced element synthesis
            form_elements = []
            for candidate in form_candidates:
                element = self._synthesize_form_element(candidate, field_rankings)
                if element:
                    form_elements.append(element)
            
            # Generate interaction strategies
            strategies = self._generate_advanced_interaction_strategies(form_candidates, field_rankings)
            
            # Create enhanced selectors
            recommended_selectors = self._create_enhanced_selectors(form_candidates, field_rankings)
            
            # Log DOM candidates with coordinates for OCR matching and training
            if self._session_storage and form_candidates:
                self._log_dom_candidates_with_coordinates(form_candidates, form_elements)
            
            return {
                "form_elements": form_elements,
                "interaction_strategies": strategies,
                "recommended_selectors": recommended_selectors,
                "form_analysis_confidence": self._calculate_form_confidence(form_candidates),
                "field_mappings": field_rankings
            }
            
        except Exception as e:
            logger.warning("Form intelligence analysis failed", exc_info=e)
            return self._get_fallback_form_intelligence(context)
    
    async def _analyze_page_content(self, page_reference, context) -> Dict[str, Any]:
        """Phase 2: Comprehensive page content analysis"""
        try:
            from calico.utils.page_text import collect_page_text_dicts
            from calico.utils.dom_regions import classify_dom_region
            
            if not page_reference:
                return self._get_fallback_page_content(context)
            
            # Collect structured text content
            text_chunks = collect_page_text_dicts(page_reference)
            
            # Analyze content structure
            content_analysis = self._analyze_content_structure(text_chunks)
            
            # Determine page purpose and type
            page_purpose = self._determine_page_purpose(text_chunks, context)
            
            # Extract navigation elements and key actions
            navigation_elements = self._extract_navigation_elements(text_chunks)
            key_actions = self._extract_key_actions(text_chunks, context)
            
            return {
                "text_chunks": text_chunks[:50],  # Limit for performance
                "content_structure": content_analysis,
                "page_purpose": page_purpose,
                "navigation_elements": navigation_elements,
                "key_actions": key_actions,
                "content_regions": self._classify_content_regions(text_chunks),
                "readability_score": self._calculate_readability_score(text_chunks)
            }
            
        except Exception as e:
            logger.warning("Page content analysis failed", exc_info=e)
            return self._get_fallback_page_content(context)
    
    async def _analyze_dom_structure(self, page_reference, context) -> Dict[str, Any]:
        """Phase 2: Advanced DOM structure analysis"""
        try:
            from calico.utils.dom_units import collect_dom_units
            
            if not page_reference:
                return self._get_fallback_dom_structure(context)
            
            # Collect logical DOM units
            dom_units = collect_dom_units(page_reference, limit=20)
            
            # Analyze interaction flow and priority
            interaction_flow = self._analyze_interaction_flow(dom_units)
            
            # Group related units
            unit_groups = self._group_related_units(dom_units)
            
            # Calculate spatial relationships
            spatial_analysis = self._analyze_spatial_relationships(dom_units)
            
            return {
                "dom_units": [unit.to_dict() for unit in dom_units],
                "interaction_flow": interaction_flow,
                "unit_groups": unit_groups,
                "spatial_analysis": spatial_analysis,
                "complexity_score": len(dom_units)
            }
            
        except Exception as e:
            logger.warning("DOM structure analysis failed", exc_info=e)
            return self._get_fallback_dom_structure(context)
    
    async def _analyze_performance_context(self, session_state, context) -> Dict[str, Any]:
        """Phase 2: Advanced performance learning and optimization"""
        try:
            history = session_state.get("history", [])
            
            # Analyze failure patterns
            failures = [event for event in history if not event.get("success", True)]
            failure_patterns = self._analyze_failure_patterns(failures)
            
            # Analyze success patterns
            successes = [event for event in history if event.get("success", True)]
            success_patterns = self._analyze_success_patterns(successes)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(history)
            
            # Generate optimization suggestions
            optimizations = self._generate_performance_optimizations(
                failure_patterns, success_patterns, context
            )
            
            # Learning from cached performance data
            cached_insights = self._get_cached_performance_insights(context.get("url", ""))
            
            return {
                "failure_patterns": failure_patterns,
                "success_patterns": success_patterns,
                "performance_metrics": performance_metrics,
                "optimizations": optimizations,
                "cached_insights": cached_insights,
                "learning_confidence": self._calculate_learning_confidence(history)
            }
            
        except Exception as e:
            logger.warning("Performance analysis failed", exc_info=e)
            return {"error": str(e), "mode": "fallback"}
    
    async def _capture_visual_context(self, session_id: str, context) -> Dict[str, Any]:
        """Phase 2: Advanced visual context with OCR integration"""
        try:
            from calico.utils.mcp_screenshot import fetch_screenshot_image
            from calico.vision.ocr import extract_text_from_image
            
            if not self.mcp_client:
                return {"available": False, "reason": "No MCP client"}
            
            # Capture screenshot
            screenshot_result = await fetch_screenshot_image(
                self.mcp_client,
                session_id=session_id,
                full_page=False  # Viewport screenshot for speed
            )
            
            visual_context = {
                "screenshot_available": True,
                "screenshot_timestamp": datetime.now().isoformat(),
                "viewport_size": screenshot_result.get("dimensions", {}),
            }
            
            # OCR text extraction
            try:
                if screenshot_result.get("image"):
                    ocr_text = await extract_text_from_image(screenshot_result["image"])
                    visual_context.update({
                        "ocr_text": ocr_text.get("text", ""),
                        "ocr_confidence": ocr_text.get("confidence", 0),
                        "detected_elements": ocr_text.get("elements", [])
                    })
            except Exception as ocr_e:
                logger.debug("OCR extraction failed", exc_info=ocr_e)
                visual_context["ocr_available"] = False
            
            # Visual layout analysis
            visual_context["layout_analysis"] = self._analyze_visual_layout(visual_context)
            
            return visual_context
            
        except Exception as e:
            logger.warning("Visual context capture failed", exc_info=e)
            return {"available": False, "error": str(e)}
    
    def _synthesize_intelligence(
        self, 
        form_intelligence, 
        page_content, 
        dom_structure, 
        performance_insights, 
        visual_context,
        goal,
        basic_context,
        session_state
    ) -> PageIntelligence:
        """Phase 2: Comprehensive intelligence synthesis"""
        
        # Determine page type with multiple data sources
        page_type = self._determine_comprehensive_page_type(
            form_intelligence, page_content, basic_context
        )
        
        # Calculate overall confidence
        confidence = self._calculate_overall_confidence(
            form_intelligence, page_content, dom_structure, visual_context
        )
        
        # Merge interaction strategies
        all_strategies = []
        all_strategies.extend(form_intelligence.get("interaction_strategies", []))
        all_strategies.extend(self._generate_content_based_strategies(page_content))
        all_strategies.extend(self._generate_structure_based_strategies(dom_structure))
        
        # Merge and enhance selectors
        all_selectors = {}
        all_selectors.update(form_intelligence.get("recommended_selectors", {}))
        all_selectors.update(self._generate_content_based_selectors(page_content))
        all_selectors.update(self._generate_visual_based_selectors(visual_context))
        
        # Create comprehensive intelligence
        return PageIntelligence(
            page_type=page_type,
            confidence=confidence,
            form_elements=form_intelligence.get("form_elements", []),
            page_content=page_content,
            dom_structure=dom_structure,
            visual_context=visual_context,
            interaction_strategies=all_strategies,
            recommended_selectors=all_selectors,
            performance_insights=performance_insights,
            telemetry_data={
                "analysis_timestamp": datetime.now().isoformat(),
                "data_sources": {
                    "form_intelligence": bool(form_intelligence),
                    "page_content": bool(page_content),
                    "dom_structure": bool(dom_structure),
                    "visual_context": bool(visual_context.get("available")),
                    "performance_data": bool(performance_insights)
                }
            }
        )
    
    async def _emit_intelligence_telemetry(self, intelligence: PageIntelligence, session_id: Optional[str]):
        """Phase 2: Emit telemetry for learning and optimization"""
        try:
            if not self.mcp_client or not session_id:
                return
                
            from calico.utils.mcp_telemetry import emit_telemetry_event
            
            await emit_telemetry_event(
                self.mcp_client,
                session_id=session_id,
                kind="reasoning",
                message="Context enhancement completed",
                data={
                    "page_type": intelligence.page_type,
                    "confidence": intelligence.confidence,
                    "form_elements_count": len(intelligence.form_elements),
                    "strategies_count": len(intelligence.interaction_strategies),
                    "selectors_count": len(intelligence.recommended_selectors),
                    "analysis_sources": intelligence.telemetry_data.get("data_sources", {})
                },
                reasoning_steps=[{
                    "step": "context_enhancement",
                    "confidence": intelligence.confidence,
                    "data_sources": len([k for k, v in intelligence.telemetry_data.get("data_sources", {}).items() if v])
                }]
            )
            
        except Exception as e:
            logger.debug("Telemetry emission failed", exc_info=e)
    
    def _create_fallback_intelligence(self, context, session_state) -> PageIntelligence:
        """Create fallback intelligence when full analysis fails"""
        url = context.get("url", "")
        
        # Basic page type detection
        page_type = "unknown"
        confidence = 0.3
        
        if "google" in url.lower():
            if "images" in url.lower():
                page_type = "google_images_search"
                confidence = 0.8
            else:
                page_type = "google_search"
                confidence = 0.8
        elif any(term in url.lower() for term in ["login", "signin", "auth"]):
            page_type = "login_page"
            confidence = 0.7
        elif "search" in url.lower():
            page_type = "search_page"
            confidence = 0.6
            
        return PageIntelligence(
            page_type=page_type,
            confidence=confidence,
            interaction_strategies=self._get_fallback_strategies(page_type),
            recommended_selectors=self._get_fallback_selectors(page_type),
            performance_insights={"mode": "fallback", "reason": "Full analysis unavailable"}
        )
    
    # === HELPER METHODS ===
    
    def _get_fallback_form_intelligence(self, context) -> Dict[str, Any]:
        """Fallback form intelligence when page analysis unavailable"""
        return {
            "form_elements": [],
            "interaction_strategies": [],
            "recommended_selectors": {},
            "form_analysis_confidence": 0.3
        }
    
    def _get_fallback_page_content(self, context) -> Dict[str, Any]:
        """Fallback page content analysis"""
        return {
            "page_purpose": "unknown",
            "content_regions": [],
            "key_actions": [],
            "readability_score": 0.5
        }
    
    def _get_fallback_dom_structure(self, context) -> Dict[str, Any]:
        """Fallback DOM structure analysis"""
        return {
            "dom_units": [],
            "interaction_flow": "unknown",
            "complexity_score": 0
        }
    
    def _determine_comprehensive_page_type(self, form_intel, content, context) -> str:
        """Determine page type using multiple intelligence sources"""
        url = context.get("url", "").lower()
        
        # URL-based detection (highest confidence)
        if "google" in url:
            return "google_images_search" if "images" in url else "google_search"
        
        # Form-based detection
        form_elements = form_intel.get("form_elements", [])
        if any(elem.get("canonical_field") == "search_input" for elem in form_elements):
            return "search_page"
        
        # Content-based detection
        page_purpose = content.get("page_purpose", "")
        if page_purpose and page_purpose != "unknown":
            return page_purpose
            
        return "general_page"
    
    def _calculate_overall_confidence(self, form_intel, content, dom_structure, visual) -> float:
        """Calculate overall confidence based on available intelligence"""
        confidence_sources = []
        
        if form_intel.get("form_analysis_confidence"):
            confidence_sources.append(form_intel["form_analysis_confidence"])
        if content.get("readability_score"):
            confidence_sources.append(content["readability_score"])
        if visual.get("available"):
            confidence_sources.append(0.8)
        if dom_structure.get("dom_units"):
            confidence_sources.append(0.7)
            
        return sum(confidence_sources) / len(confidence_sources) if confidence_sources else 0.3
    
    def _synthesize_form_element(self, candidate, rankings) -> Optional[Dict[str, Any]]:
        """Enhanced form element synthesis"""
        fuzzy_matches = candidate.get("fuzzy_matches", [])
        if not fuzzy_matches:
            return None
            
        best_match = max(fuzzy_matches, key=lambda m: m.get("score", 0))
        canonical_field = best_match.get("field")
        
        # Build comprehensive selector list
        selectors = []
        
        # Primary selectors
        for attr in ["name", "id"]:
            if candidate.get(attr):
                selectors.append(f'[{attr}="{candidate[attr]}"]')
                
        # Type-based selectors
        if candidate.get("type"):
            selectors.append(f'input[type="{candidate["type"]}"]')
            
        # Semantic selectors based on canonical field
        selectors.extend(self._get_semantic_selectors(canonical_field))
        
        # Extract bounding box coordinates
        bounding_box = candidate.get("bounding_box")
        coordinates = None
        if bounding_box:
            # Normalize bounding box format for consistency
            coordinates = {
                "x": bounding_box.get("left", bounding_box.get("x", 0)),
                "y": bounding_box.get("top", bounding_box.get("y", 0)),
                "width": bounding_box.get("width", 0),
                "height": bounding_box.get("height", 0),
                "right": bounding_box.get("right"),
                "bottom": bounding_box.get("bottom")
            }
        
        return {
            "canonical_field": canonical_field,
            "confidence": best_match.get("score", 0),
            "selectors": selectors,
            "enhanced_selector": ", ".join(selectors),
            "element_info": {
                "tag": candidate.get("tag"),
                "type": candidate.get("type"),
                "name": candidate.get("name"),
                "id": candidate.get("id"),
                "label": candidate.get("label"),
                "placeholder": candidate.get("placeholder")
            },
            "coordinates": coordinates,  # Added for OCR matching
            "bounding_box": bounding_box,  # Keep original format
            "interaction_ready": True,
            "priority": self._calculate_element_priority(canonical_field, best_match)
        }
    
    def _get_semantic_selectors(self, field_type: str) -> List[str]:
        """Get semantic selectors for field types"""
        selectors_map = {
            "search_input": [
                'input[type="search"]',
                'input[placeholder*="search" i]',
                '[aria-label*="search" i]',
                '[role="searchbox"]',
                '#search-input'
            ],
            "email": [
                'input[type="email"]',
                'input[placeholder*="email" i]',
                '[aria-label*="email" i]'
            ],
            "password": [
                'input[type="password"]',
                'input[placeholder*="password" i]',
                '[aria-label*="password" i]'
            ]
        }
        
        return selectors_map.get(field_type, [])
    
    def _calculate_element_priority(self, field_type: str, match_data: Dict) -> str:
        """Calculate interaction priority for elements"""
        confidence = match_data.get("score", 0)
        
        if field_type in ["search_input", "email", "password"] and confidence > 80:
            return "critical"
        elif confidence > 60:
            return "high"
        elif confidence > 40:
            return "medium"
        else:
            return "low"
    
    # Placeholder methods for comprehensive analysis
    def _generate_advanced_interaction_strategies(self, candidates, rankings) -> List[Dict]:
        return []
    
    def _create_enhanced_selectors(self, candidates, rankings) -> Dict[str, str]:
        return {}
    
    def _calculate_form_confidence(self, candidates) -> float:
        return 0.5
    
    def _analyze_content_structure(self, text_chunks) -> Dict:
        return {}
    
    def _determine_page_purpose(self, text_chunks, context) -> str:
        return "unknown"
    
    def _extract_navigation_elements(self, text_chunks) -> List:
        return []
    
    def _extract_key_actions(self, text_chunks, context) -> List:
        return []
    
    def _classify_content_regions(self, text_chunks) -> List:
        return []
    
    def _calculate_readability_score(self, text_chunks) -> float:
        return 0.5
    
    def _analyze_interaction_flow(self, dom_units) -> str:
        return "top_to_bottom"
    
    def _group_related_units(self, dom_units) -> List:
        return []
    
    def _analyze_spatial_relationships(self, dom_units) -> Dict:
        return {}
    
    def _analyze_failure_patterns(self, failures) -> List:
        return []
    
    def _analyze_success_patterns(self, successes) -> List:
        return []
    
    def _calculate_performance_metrics(self, history) -> Dict:
        return {}
    
    def _generate_performance_optimizations(self, failures, successes, context) -> List:
        return []
    
    def _get_cached_performance_insights(self, url) -> Dict:
        return self._performance_cache.get(url, {})
    
    def _calculate_learning_confidence(self, history) -> float:
        return len(history) / 20.0 if history else 0.0
    
    def _analyze_visual_layout(self, visual_context) -> Dict:
        return {}
    
    def _generate_content_based_strategies(self, content) -> List:
        return []
    
    def _generate_structure_based_strategies(self, structure) -> List:
        return []
    
    def _generate_content_based_selectors(self, content) -> Dict:
        return {}
    
    def _generate_visual_based_selectors(self, visual) -> Dict:
        return {}
    
    def _get_fallback_strategies(self, page_type) -> List:
        """Enhanced fallback strategies for Phase 2"""
        strategies = {
            "google_images_search": [
                {
                    "type": "search_interaction",
                    "strategy": "Multi-modal Google Images search with visual confirmation",
                    "priority": "critical",
                    "approach": "enhanced_selector_cascade_with_visual_validation"
                }
            ],
            "walmart_search": [
                {
                    "type": "ecommerce_interaction",
                    "strategy": "Walmart product search and navigation using data-item-id attributes",
                    "priority": "high",
                    "approach": "data_attribute_targeting",
                    "notes": "Use [data-item-id] to identify individual product items"
                }
            ],
            "ecommerce_general": [
                {
                    "type": "ecommerce_interaction",
                    "strategy": "General e-commerce product browsing with data attribute fallbacks",
                    "priority": "medium",
                    "approach": "multi_attribute_cascade"
                }
            ]
        }
        return strategies.get(page_type, [])
    
    def _get_fallback_selectors(self, page_type) -> Dict[str, str]:
        """Enhanced fallback selectors for Phase 2"""
        selectors = {
            "google_search": {
                "search_input": 'input[name="q"], input[type="search"], input[aria-label*="search" i], textarea[name="q"], #search-input, [role="searchbox"]',
                "search_results": 'div[data-ved], div.g, .tF2Cxc, [data-result-index], .kvH3mc, .MjjYud, .hlcw0c, div[jscontroller][lang], .yuRUbf, div.kvH3mc div.Z26q7c, div[data-async-context], .ULSxyf'
            },
            "google_images_search": {
                "search_input": 'input[name="q"], textarea[name="q"], input[type="search"], [role="searchbox"], input[aria-label*="search" i], #search-input, input[placeholder*="search" i]',
                "search_results": 'div[data-ved], .rg_i, .isv-r, div[jsname], [data-result-index], .mNsIhb, div[data-ri], .bRMDJf, .islir, div[data-async-context]'
            },
            "walmart_search": {
                "search_input": 'input[name="q"], input[type="search"], input[aria-label*="search" i], #search-box-input, input[placeholder*="search" i]',
                "search_results_container": '[data-testid="list-view"], [data-testid="search-results"], #search-result-container',
                "search_results": '[data-item-id]',  # Wait for individual items
                "product_items": '[data-item-id], div[role="group"][data-item-id]',  # Individual commerce items
                "product_links": 'a[link-identifier], a[href*="/ip/"]',
                "product_titles": '[data-automation-id="product-title"], span.normal.dark-gray',
                "product_prices": '[data-automation-id="product-price"], div.b.black.green'
            },
            "ecommerce_general": {
                "search_input": 'input[name="q"], input[type="search"], input[aria-label*="search" i], input[placeholder*="search" i], #search-input',
                "product_items": '[data-item-id], [data-product-id], .product-item, .product-card, [data-testid*="product"]',
                "product_links": 'a[data-item-id], a.product-link, a[data-product-id]',
                "add_to_cart": 'button[data-automation-id="add-to-cart"], button[aria-label*="add to cart" i], button:has-text("Add to Cart")'
            }
        }
        return selectors.get(page_type, {})
    
    def _log_dom_candidates_with_coordinates(self, form_candidates: List[Dict[str, Any]], form_elements: List[Dict[str, Any]]) -> None:
        """
        Log DOM candidates with their x, y coordinates for OCR matching and training.
        
        Args:
            form_candidates: Raw form candidates with bounding_box data
            form_elements: Synthesized form elements with normalized coordinates
        """
        if not self._session_storage:
            return
        
        try:
            # Prepare candidates data with coordinates
            candidates_with_coords = []
            
            for candidate in form_candidates:
                bounding_box = candidate.get("bounding_box")
                if not bounding_box:
                    continue
                
                # Normalize coordinates
                coords = {
                    "x": bounding_box.get("left", bounding_box.get("x", 0)),
                    "y": bounding_box.get("top", bounding_box.get("y", 0)),
                    "width": bounding_box.get("width", 0),
                    "height": bounding_box.get("height", 0),
                    "right": bounding_box.get("right"),
                    "bottom": bounding_box.get("bottom")
                }
                
                candidate_data = {
                    "tag": candidate.get("tag"),
                    "type": candidate.get("type"),
                    "name": candidate.get("name"),
                    "id": candidate.get("id"),
                    "label": candidate.get("label"),
                    "placeholder": candidate.get("placeholder"),
                    "canonical_field": candidate.get("canonical_field"),
                    "score": candidate.get("score", 0),
                    "coordinates": coords,
                    "bounding_box": bounding_box,  # Keep original format for OCR matching
                    "fuzzy_matches_count": len(candidate.get("fuzzy_matches", []))
                }
                
                candidates_with_coords.append(candidate_data)
            
            # Save to training data with timestamp
            training_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "dom_candidates_with_coordinates",
                "total_candidates": len(form_candidates),
                "candidates_with_coords": len(candidates_with_coords),
                "candidates": candidates_with_coords,
                "synthesized_elements_count": len(form_elements)
            }
            
            self._session_storage.save_training_data(
                data=training_data,
                data_type="dom_candidates_coords"
            )
            
            # Also log summary
            self._session_storage.save_log(
                f"Logged {len(candidates_with_coords)} DOM candidates with coordinates for OCR matching",
                log_type="dom",
                level="INFO"
            )
            
            logger.info(f"Saved DOM candidates with coordinates: {len(candidates_with_coords)} elements", extra={
                "total_candidates": len(form_candidates),
                "with_coordinates": len(candidates_with_coords),
                "synthesized_elements": len(form_elements)
            })
            
        except Exception as e:
            logger.error(f"Failed to log DOM candidates with coordinates: {e}", exc_info=True)
