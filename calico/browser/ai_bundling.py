"""AI-powered task bundling that converts natural language prompts into executable bundles."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

from calico.browser.bundling import (
    TaskBundle, BundledTask, TaskSiteConfig, 
    get_bundle_builder, get_bundle_executor
)
from calico.browser.site_configs import register_all_job_sites
from calico.browser.actions import (
    NavigateAction, ClickAction, FillAction, WaitAction, 
    ScreenshotAction, TypeAction
)
from calico.browser.workflow import BrowserWorkflowSpec

logger = logging.getLogger(__name__)


@dataclass
class TaskIntent:
    """Structured representation of user intent for task bundling."""
    
    task_type: str  # job_application, data_collection, form_filling, etc.
    target_sites: List[str]
    parameters: Dict[str, Any]
    constraints: Dict[str, Any]
    success_criteria: List[str]


class AIBundlingAgent:
    """AI agent that creates task bundles from natural language prompts."""
    
    def __init__(self):
        self.builder = get_bundle_builder()
        self.executor = get_bundle_executor()
        self._initialize_site_configs()
        
    def _initialize_site_configs(self):
        """Initialize with pre-configured site configs."""
        register_all_job_sites(self.builder)
        logger.info("AI Bundling Agent initialized with job site configurations")
    
    async def process_prompt(self, prompt: str) -> TaskBundle:
        """Process a natural language prompt and create a task bundle."""
        
        logger.info(f"Processing AI prompt: {prompt}")
        
        # Parse the prompt to extract intent
        intent = self._parse_prompt(prompt)
        
        # Create task bundle based on intent
        bundle = await self._create_bundle_from_intent(intent)
        
        return bundle
    
    def _parse_prompt(self, prompt: str) -> TaskIntent:
        """Parse natural language prompt into structured intent."""
        
        prompt_lower = prompt.lower()
        
        # Detect task type
        task_type = "generic"
        if any(keyword in prompt_lower for keyword in ["job", "application", "apply", "career"]):
            task_type = "job_application"
        elif any(keyword in prompt_lower for keyword in ["scrape", "collect", "gather", "extract"]):
            task_type = "data_collection"
        elif any(keyword in prompt_lower for keyword in ["fill", "form", "submit", "register"]):
            task_type = "form_filling"
        
        # Extract target sites
        target_sites = self._extract_sites_from_prompt(prompt)
        
        # Extract parameters based on task type
        parameters = self._extract_parameters(prompt, task_type)
        
        # Extract constraints
        constraints = self._extract_constraints(prompt)
        
        # Define success criteria
        success_criteria = self._define_success_criteria(task_type)
        
        intent = TaskIntent(
            task_type=task_type,
            target_sites=target_sites,
            parameters=parameters,
            constraints=constraints,
            success_criteria=success_criteria
        )
        
        logger.info(f"Parsed intent: {intent.task_type} on {len(intent.target_sites)} sites")
        return intent
    
    def _extract_sites_from_prompt(self, prompt: str) -> List[str]:
        """Extract target sites from the prompt."""
        
        # Known site mappings
        site_mappings = {
            "indeed": ["indeed"],
            "ziprecruiter": ["ziprecruiter", "zip recruiter"],
            "linkedin": ["linkedin", "linked in"],
            "glassdoor": ["glassdoor", "glass door"],
            "monster": ["monster"],
            "dice": ["dice"],
            "careerbuilder": ["careerbuilder", "career builder"],
            "angellist": ["angellist", "angel list", "wellfound"],
            "stackoverflow": ["stackoverflow", "stack overflow", "so jobs"],
            "github": ["github jobs"],
        }
        
        found_sites = []
        prompt_lower = prompt.lower()
        
        for site, keywords in site_mappings.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    found_sites.append(site)
                    break
        
        # If no specific sites mentioned, use default job sites
        if not found_sites and "job" in prompt_lower:
            found_sites = ["indeed", "ziprecruiter", "linkedin", "glassdoor"]
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(found_sites))
    
    def _extract_parameters(self, prompt: str, task_type: str) -> Dict[str, Any]:
        """Extract task parameters from the prompt."""
        
        parameters = {}
        
        if task_type == "job_application":
            # Extract job-related parameters
            parameters.update(self._extract_job_parameters(prompt))
        elif task_type == "data_collection":
            parameters.update(self._extract_data_collection_parameters(prompt))
        elif task_type == "form_filling":
            parameters.update(self._extract_form_parameters(prompt))
        
        return parameters
    
    def _extract_job_parameters(self, prompt: str) -> Dict[str, Any]:
        """Extract job application parameters."""
        
        parameters = {}
        
        # Extract position/role
        role_patterns = [
            r"(?:for|as|position|role|job)\s+(?:a\s+)?([^,\n\.]+?)(?:\s+(?:in|at|on|,))",
            r"([a-zA-Z\s]+)\s+(?:position|role|job)",
        ]
        
        for pattern in role_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                parameters["position"] = match.group(1).strip()
                break
        
        # Extract location
        location_patterns = [
            r"(?:in|at|location)\s+([^,\n\.]+)",
            r"(?:remote|onsite|hybrid)",
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                parameters["location"] = match.group(0).strip()
                break
        
        # Extract experience level
        if any(word in prompt.lower() for word in ["senior", "sr", "lead"]):
            parameters["experience_level"] = "senior"
        elif any(word in prompt.lower() for word in ["junior", "jr", "entry"]):
            parameters["experience_level"] = "junior"
        else:
            parameters["experience_level"] = "mid"
        
        # Extract salary if mentioned
        salary_match = re.search(r"\$(\d+[,\d]*)", prompt)
        if salary_match:
            parameters["salary_requirement"] = salary_match.group(0)
        
        return parameters
    
    def _extract_data_collection_parameters(self, prompt: str) -> Dict[str, Any]:
        """Extract data collection parameters."""
        
        parameters = {}
        
        # Extract what to collect
        collect_patterns = [
            r"collect\s+([^,\n\.]+)",
            r"scrape\s+([^,\n\.]+)",
            r"gather\s+([^,\n\.]+)",
        ]
        
        for pattern in collect_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                parameters["data_type"] = match.group(1).strip()
                break
        
        return parameters
    
    def _extract_form_parameters(self, prompt: str) -> Dict[str, Any]:
        """Extract form filling parameters."""
        
        parameters = {}
        
        # Extract form type
        if "registration" in prompt.lower() or "register" in prompt.lower():
            parameters["form_type"] = "registration"
        elif "contact" in prompt.lower():
            parameters["form_type"] = "contact"
        elif "survey" in prompt.lower():
            parameters["form_type"] = "survey"
        
        return parameters
    
    def _extract_constraints(self, prompt: str) -> Dict[str, Any]:
        """Extract execution constraints from the prompt."""
        
        constraints = {}
        
        # Extract concurrency preferences
        if any(word in prompt.lower() for word in ["parallel", "simultaneously", "concurrent"]):
            constraints["max_concurrent"] = 5
        elif any(word in prompt.lower() for word in ["sequential", "one by one", "separately"]):
            constraints["max_concurrent"] = 1
        else:
            constraints["max_concurrent"] = 3  # Default
        
        # Extract failure handling
        if any(phrase in prompt.lower() for phrase in ["stop on failure", "fail fast"]):
            constraints["fail_fast"] = True
        else:
            constraints["fail_fast"] = False
        
        # Extract timeout preferences  
        if "quick" in prompt.lower() or "fast" in prompt.lower():
            constraints["timeout"] = 30
        elif "thorough" in prompt.lower() or "careful" in prompt.lower():
            constraints["timeout"] = 120
        else:
            constraints["timeout"] = 60
        
        return constraints
    
    def _define_success_criteria(self, task_type: str) -> List[str]:
        """Define success criteria based on task type."""
        
        if task_type == "job_application":
            return [
                "Successfully navigate to job site",
                "Find relevant job listings", 
                "Complete application process",
                "Receive confirmation or save application"
            ]
        elif task_type == "data_collection":
            return [
                "Successfully access target pages",
                "Extract required data elements",
                "Save collected data",
                "Verify data completeness"
            ]
        elif task_type == "form_filling":
            return [
                "Locate target forms",
                "Fill all required fields",
                "Submit forms successfully",
                "Receive confirmation"
            ]
        else:
            return [
                "Complete all specified actions",
                "Handle errors gracefully",
                "Provide execution summary"
            ]
    
    async def _create_bundle_from_intent(self, intent: TaskIntent) -> TaskBundle:
        """Create an executable task bundle from parsed intent."""
        
        if intent.task_type == "job_application":
            return self._create_job_application_bundle(intent)
        elif intent.task_type == "data_collection":
            return self._create_data_collection_bundle(intent)
        elif intent.task_type == "form_filling":
            return self._create_form_filling_bundle(intent)
        else:
            return self._create_generic_bundle(intent)
    
    def _create_job_application_bundle(self, intent: TaskIntent) -> TaskBundle:
        """Create a job application bundle."""
        
        # Use the builder's job application method
        bundle = self.builder.create_job_application_bundle(
            sites=intent.target_sites,
            application_data=intent.parameters,
            max_concurrent=intent.constraints.get("max_concurrent", 3)
        )
        
        # Update bundle properties based on intent
        bundle.description = f"AI-generated job applications: {intent.parameters.get('position', 'various positions')}"
        bundle.fail_fast = intent.constraints.get("fail_fast", False)
        
        return bundle
    
    def _create_data_collection_bundle(self, intent: TaskIntent) -> TaskBundle:
        """Create a data collection bundle."""
        
        tasks = []
        
        for site in intent.target_sites:
            # Create basic data collection workflow
            actions = [
                NavigateAction(url=f"https://{site}.com"),
                WaitAction(condition_type="load_state", condition_value="networkidle"),
                ScreenshotAction(path=f"data_collection_{site}.png"),
                # Add site-specific collection logic here
            ]
            
            site_config = TaskSiteConfig(
                site_name=site,
                base_url=f"https://{site}.com",
                custom_actions=actions
            )
            
            workflow_spec = BrowserWorkflowSpec(
                browser_actions=actions,
                description=f"Data collection from {site}"
            )
            
            task = BundledTask(
                task_id=f"collect_{site}",
                site_config=site_config,
                workflow_spec=workflow_spec
            )
            
            tasks.append(task)
        
        bundle = TaskBundle(
            bundle_id=f"data_collection_{hash(str(intent.target_sites))}",
            description=f"Data collection from {len(intent.target_sites)} sites",
            tasks=tasks,
            max_concurrent_tasks=intent.constraints.get("max_concurrent", 3),
            fail_fast=intent.constraints.get("fail_fast", False)
        )
        
        return bundle
    
    def _create_form_filling_bundle(self, intent: TaskIntent) -> TaskBundle:
        """Create a form filling bundle."""
        
        tasks = []
        
        for site in intent.target_sites:
            actions = [
                NavigateAction(url=f"https://{site}.com"),
                WaitAction(condition_type="load_state", condition_value="networkidle"),
                # Add form filling logic based on parameters
                ScreenshotAction(path=f"form_filled_{site}.png"),
            ]
            
            site_config = TaskSiteConfig(
                site_name=site,
                base_url=f"https://{site}.com", 
                custom_actions=actions
            )
            
            workflow_spec = BrowserWorkflowSpec(
                browser_actions=actions,
                description=f"Form filling on {site}"
            )
            
            task = BundledTask(
                task_id=f"form_{site}",
                site_config=site_config,
                workflow_spec=workflow_spec
            )
            
            tasks.append(task)
        
        bundle = TaskBundle(
            bundle_id=f"form_filling_{hash(str(intent.target_sites))}",
            description=f"Form filling on {len(intent.target_sites)} sites",
            tasks=tasks,
            max_concurrent_tasks=intent.constraints.get("max_concurrent", 3),
            fail_fast=intent.constraints.get("fail_fast", False)
        )
        
        return bundle
    
    def _create_generic_bundle(self, intent: TaskIntent) -> TaskBundle:
        """Create a generic bundle for unspecified tasks."""
        
        tasks = []
        
        for site in intent.target_sites:
            actions = [
                NavigateAction(url=f"https://{site}.com"),
                WaitAction(condition_type="load_state", condition_value="networkidle"),
                ScreenshotAction(path=f"generic_{site}.png"),
            ]
            
            site_config = TaskSiteConfig(
                site_name=site,
                base_url=f"https://{site}.com",
                custom_actions=actions
            )
            
            workflow_spec = BrowserWorkflowSpec(
                browser_actions=actions,
                description=f"Generic task on {site}"
            )
            
            task = BundledTask(
                task_id=f"generic_{site}",
                site_config=site_config,
                workflow_spec=workflow_spec
            )
            
            tasks.append(task)
        
        bundle = TaskBundle(
            bundle_id=f"generic_{hash(str(intent.target_sites))}",
            description=f"Generic tasks on {len(intent.target_sites)} sites",
            tasks=tasks,
            max_concurrent_tasks=intent.constraints.get("max_concurrent", 3),
            fail_fast=intent.constraints.get("fail_fast", False)
        )
        
        return bundle
    
    async def execute_prompt(self, prompt: str) -> TaskBundle:
        """Process and execute a natural language prompt end-to-end."""
        
        # Create bundle from prompt
        bundle = await self.process_prompt(prompt)
        
        # Execute the bundle
        result_bundle = await self.executor.execute_bundle(bundle)
        
        return result_bundle
    
    def explain_bundle(self, bundle: TaskBundle) -> str:
        """Generate human-readable explanation of a task bundle."""
        
        explanation = f"Task Bundle: {bundle.description}\n"
        explanation += f"Total Tasks: {len(bundle.tasks)}\n"
        explanation += f"Max Concurrent: {bundle.max_concurrent_tasks}\n"
        explanation += f"Fail Fast: {bundle.fail_fast}\n\n"
        
        explanation += "Tasks:\n"
        for i, task in enumerate(bundle.tasks, 1):
            explanation += f"  {i}. {task.site_config.site_name}: {task.workflow_spec.description}\n"
        
        return explanation


# Global AI bundling agent
_ai_agent = AIBundlingAgent()


def get_ai_bundling_agent() -> AIBundlingAgent:
    """Get the global AI bundling agent."""
    return _ai_agent