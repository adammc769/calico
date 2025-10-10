"""Task bundling system for distributed browser automation workflows."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from datetime import datetime, UTC

from calico.browser.actions import BrowserAction
from calico.browser.automation import BrowserSession, BrowserAutomation, BrowserConfig
from calico.browser.workflow import BrowserWorkflowSpec, BrowserWorkflowExecutor, WorkflowResult

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a bundled task."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BundleStatus(Enum):
    """Status of a task bundle."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskSiteConfig:
    """Configuration for a specific site's automation."""
    
    site_name: str
    base_url: str
    browser_config: Optional[BrowserConfig] = None
    custom_actions: List[BrowserAction] = field(default_factory=list)
    retry_attempts: int = 3
    timeout_seconds: int = 300
    required_cookies: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.browser_config is None:
            self.browser_config = BrowserConfig(
                headless=True,
                browser_type="chromium",
                timeout=self.timeout_seconds * 1000
            )


@dataclass 
class BundledTask:
    """Individual task within a bundle."""
    
    task_id: str
    site_config: TaskSiteConfig
    workflow_spec: BrowserWorkflowSpec
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[WorkflowResult] = None
    error: Optional[str] = None
    attempts: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())


@dataclass
class TaskBundle:
    """Collection of independent tasks that can run in parallel."""
    
    bundle_id: str
    description: str
    tasks: List[BundledTask]
    status: BundleStatus = BundleStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    max_concurrent_tasks: int = 5
    fail_fast: bool = False  # If True, cancel remaining tasks on first failure
    
    def __post_init__(self):
        if not self.bundle_id:
            self.bundle_id = str(uuid.uuid4())
    
    @property
    def completed_tasks(self) -> List[BundledTask]:
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
    
    @property 
    def failed_tasks(self) -> List[BundledTask]:
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]
    
    @property
    def running_tasks(self) -> List[BundledTask]:
        return [t for t in self.tasks if t.status == TaskStatus.RUNNING]
    
    @property
    def pending_tasks(self) -> List[BundledTask]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]
    
    @property
    def success_rate(self) -> float:
        if not self.tasks:
            return 0.0
        return len(self.completed_tasks) / len(self.tasks)


class TaskBundleExecutor:
    """Executes task bundles with parallel execution and fault tolerance."""
    
    def __init__(self):
        self._automation_instances: Dict[str, BrowserAutomation] = {}
        self._workflow_executors: Dict[str, BrowserWorkflowExecutor] = {}
        self._running_bundles: Dict[str, TaskBundle] = {}
        
    async def execute_bundle(
        self,
        bundle: TaskBundle,
        progress_callback: Optional[Callable[[TaskBundle], Awaitable[None]]] = None
    ) -> TaskBundle:
        """Execute a task bundle with parallel execution."""
        
        logger.info(f"Starting bundle execution: {bundle.bundle_id} - {bundle.description}")
        
        bundle.status = BundleStatus.RUNNING
        bundle.started_at = datetime.now(UTC)
        self._running_bundles[bundle.bundle_id] = bundle
        
        try:
            # Create semaphore to limit concurrent tasks
            semaphore = asyncio.Semaphore(bundle.max_concurrent_tasks)
            
            # Create task coroutines
            task_coroutines = [
                self._execute_single_task(task, bundle, semaphore, progress_callback)
                for task in bundle.tasks
            ]
            
            # Execute tasks concurrently
            await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            # Determine final bundle status
            await self._finalize_bundle_status(bundle)
            
        except Exception as e:
            logger.error(f"Bundle execution error: {e}")
            bundle.status = BundleStatus.FAILED
            
        finally:
            bundle.completed_at = datetime.now(UTC)
            if bundle.bundle_id in self._running_bundles:
                del self._running_bundles[bundle.bundle_id]
                
            # Clean up automation instances for this bundle
            await self._cleanup_bundle_resources(bundle)
            
        logger.info(f"Bundle completed: {bundle.bundle_id} - Status: {bundle.status.value}")
        return bundle
    
    async def _execute_single_task(
        self,
        task: BundledTask,
        bundle: TaskBundle,
        semaphore: asyncio.Semaphore,
        progress_callback: Optional[Callable[[TaskBundle], Awaitable[None]]]
    ):
        """Execute a single bundled task."""
        
        async with semaphore:
            # Check if bundle was cancelled or failed fast
            if bundle.status in [BundleStatus.CANCELLED, BundleStatus.FAILED]:
                task.status = TaskStatus.CANCELLED
                return
                
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now(UTC)
                task.attempts += 1
                
                logger.info(f"Executing task {task.task_id} for site: {task.site_config.site_name}")
                
                # Get or create automation instance for this site
                automation = await self._get_automation_for_site(task.site_config)
                session = await automation.create_session(task.site_config.browser_config)
                task.session_id = session.page.url or str(uuid.uuid4())
                
                # Get workflow executor
                executor = self._get_workflow_executor(task.site_config.site_name)
                executor.register_session(task.task_id, session)
                
                try:
                    # Execute the workflow
                    result = await executor.execute_workflow_spec(task.workflow_spec)
                    task.result = result
                    
                    if result.success:
                        task.status = TaskStatus.COMPLETED
                        logger.info(f"Task completed successfully: {task.task_id}")
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = result.error
                        logger.error(f"Task failed: {task.task_id} - {result.error}")
                        
                        # Retry logic
                        if task.attempts < task.site_config.retry_attempts:
                            logger.info(f"Retrying task {task.task_id} (attempt {task.attempts + 1})")
                            await asyncio.sleep(2 ** task.attempts)  # Exponential backoff
                            await self._execute_single_task(task, bundle, semaphore, progress_callback)
                            return
                            
                finally:
                    executor.unregister_session(task.task_id)
                    await automation.close_session(session)
                    
            except Exception as e:
                logger.error(f"Task execution error {task.task_id}: {e}")
                task.status = TaskStatus.FAILED
                task.error = str(e)
                
                # Retry on exception
                if task.attempts < task.site_config.retry_attempts:
                    logger.info(f"Retrying task {task.task_id} after exception")
                    await asyncio.sleep(2 ** task.attempts)
                    await self._execute_single_task(task, bundle, semaphore, progress_callback)
                    return
                    
            finally:
                task.completed_at = datetime.now(UTC)
                
                # Check fail-fast condition
                if bundle.fail_fast and task.status == TaskStatus.FAILED:
                    logger.warning(f"Fail-fast triggered by task {task.task_id}")
                    bundle.status = BundleStatus.FAILED
                    await self._cancel_remaining_tasks(bundle)
                    
                # Call progress callback if provided
                if progress_callback:
                    try:
                        await progress_callback(bundle)
                    except Exception as e:
                        logger.error(f"Progress callback error: {e}")
    
    async def _get_automation_for_site(self, site_config: TaskSiteConfig) -> BrowserAutomation:
        """Get or create browser automation instance for a site."""
        
        if site_config.site_name not in self._automation_instances:
            automation = BrowserAutomation(site_config.browser_config)
            await automation.__aenter__()
            self._automation_instances[site_config.site_name] = automation
            
        return self._automation_instances[site_config.site_name]
    
    def _get_workflow_executor(self, site_name: str) -> BrowserWorkflowExecutor:
        """Get or create workflow executor for a site."""
        
        if site_name not in self._workflow_executors:
            self._workflow_executors[site_name] = BrowserWorkflowExecutor()
            
        return self._workflow_executors[site_name]
    
    async def _finalize_bundle_status(self, bundle: TaskBundle):
        """Determine final status of the bundle based on task results."""
        
        completed = len(bundle.completed_tasks)
        failed = len(bundle.failed_tasks)
        total = len(bundle.tasks)
        
        if completed == total:
            bundle.status = BundleStatus.COMPLETED
        elif completed > 0:
            bundle.status = BundleStatus.PARTIAL_SUCCESS
        elif failed == total:
            bundle.status = BundleStatus.FAILED
        else:
            bundle.status = BundleStatus.FAILED
    
    async def _cancel_remaining_tasks(self, bundle: TaskBundle):
        """Cancel all pending and running tasks in a bundle."""
        
        for task in bundle.tasks:
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(UTC)
    
    async def _cleanup_bundle_resources(self, bundle: TaskBundle):
        """Clean up resources used by a bundle."""
        
        # Note: We keep automation instances alive for reuse
        # They will be cleaned up when the executor is destroyed
        pass
    
    async def cancel_bundle(self, bundle_id: str) -> bool:
        """Cancel a running bundle."""
        
        if bundle_id not in self._running_bundles:
            return False
            
        bundle = self._running_bundles[bundle_id]
        bundle.status = BundleStatus.CANCELLED
        await self._cancel_remaining_tasks(bundle)
        
        logger.info(f"Bundle cancelled: {bundle_id}")
        return True
    
    def get_bundle_status(self, bundle_id: str) -> Optional[TaskBundle]:
        """Get current status of a bundle."""
        
        return self._running_bundles.get(bundle_id)
    
    async def cleanup(self):
        """Clean up all resources."""
        
        # Cancel running bundles
        for bundle_id in list(self._running_bundles.keys()):
            await self.cancel_bundle(bundle_id)
            
        # Close automation instances  
        for automation in self._automation_instances.values():
            try:
                await automation.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing automation: {e}")
                
        self._automation_instances.clear()
        self._workflow_executors.clear()


class TaskBundleBuilder:
    """Builder for creating task bundles from high-level descriptions."""
    
    def __init__(self):
        self._site_configs: Dict[str, TaskSiteConfig] = {}
        
    def register_site_config(self, config: TaskSiteConfig):
        """Register a site configuration for use in bundles."""
        
        self._site_configs[config.site_name] = config
        logger.info(f"Registered site config: {config.site_name}")
    
    def create_job_application_bundle(
        self,
        sites: List[str],
        application_data: Dict[str, Any],
        max_concurrent: int = 3
    ) -> TaskBundle:
        """Create a bundle for job applications across multiple sites."""
        
        tasks = []
        
        for site_name in sites:
            if site_name not in self._site_configs:
                logger.warning(f"Site config not found: {site_name}")
                continue
                
            site_config = self._site_configs[site_name]
            
            # Create workflow spec for this site
            workflow_spec = self._create_job_application_workflow(
                site_config, 
                application_data
            )
            
            task = BundledTask(
                task_id=f"job_app_{site_name}_{uuid.uuid4().hex[:8]}",
                site_config=site_config,
                workflow_spec=workflow_spec
            )
            
            tasks.append(task)
        
        bundle = TaskBundle(
            bundle_id=f"job_apps_{uuid.uuid4().hex[:8]}",
            description=f"Job applications on {len(tasks)} sites",
            tasks=tasks,
            max_concurrent_tasks=max_concurrent
        )
        
        return bundle
    
    def _create_job_application_workflow(
        self,
        site_config: TaskSiteConfig,
        application_data: Dict[str, Any]
    ) -> BrowserWorkflowSpec:
        """Create a workflow spec for job application on a specific site."""
        
        from calico.browser.actions import NavigateAction, FillAction, ClickAction, ScreenshotAction
        
        # Base actions that work for most job sites
        base_actions = [
            NavigateAction(url=site_config.base_url),
            # Site-specific actions would be added here based on site_config
        ]
        
        # Add custom actions for this site
        actions = base_actions + site_config.custom_actions
        
        # Add screenshot for verification
        actions.append(ScreenshotAction(path=f"job_app_{site_config.site_name}.png"))
        
        return BrowserWorkflowSpec(
            browser_actions=actions,
            description=f"Job application workflow for {site_config.site_name}"
        )


# Global instances
_bundle_executor = TaskBundleExecutor()
_bundle_builder = TaskBundleBuilder()


def get_bundle_executor() -> TaskBundleExecutor:
    """Get the global task bundle executor."""
    return _bundle_executor


def get_bundle_builder() -> TaskBundleBuilder:
    """Get the global task bundle builder."""
    return _bundle_builder