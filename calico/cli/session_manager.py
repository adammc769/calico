"""Session management for Calico CLI with multi-session support."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Status of a session."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class SessionInfo:
    """Information about a session."""
    session_id: int
    goal: Optional[str] = None
    status: SessionStatus = SessionStatus.IDLE
    task: Optional[asyncio.Task] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    gpt_logs: List[str] = field(default_factory=list)
    playwright_logs: List[str] = field(default_factory=list)
    action_logs: List[str] = field(default_factory=list)
    server_logs: List[str] = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    completed_tasks: int = 0
    hang_detected: bool = False
    last_activity: datetime = field(default_factory=datetime.now)
    verbose_mode: bool = False  # Debug/trace mode flag
    trace_data: Dict = field(default_factory=dict)  # Store detailed trace data
    
    def add_gpt_log(self, message: str):
        """Add a GPT log message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gpt_logs.append(f"[{timestamp}] {message}")
        self.last_activity = datetime.now()
        
    def add_playwright_log(self, message: str):
        """Add a Playwright log message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.playwright_logs.append(f"[{timestamp}] {message}")
        self.last_activity = datetime.now()
        
    def add_action_log(self, message: str):
        """Add an action log message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.action_logs.append(f"[{timestamp}] {message}")
        self.last_activity = datetime.now()
    
    def add_server_log(self, message: str):
        """Add a server log message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.server_logs.append(f"[{timestamp}] {message}")
        self.last_activity = datetime.now()
    
    def increment_completed_tasks(self):
        """Increment the completed tasks counter."""
        self.completed_tasks += 1
    
    def check_for_hang(self, timeout_seconds: int = 300) -> bool:
        """Check if session appears to be hung."""
        if self.status in [SessionStatus.PLANNING, SessionStatus.EXECUTING]:
            time_since_activity = (datetime.now() - self.last_activity).total_seconds()
            self.hang_detected = time_since_activity > timeout_seconds
            return self.hang_detected
        return False


class SessionManager:
    """Manages multiple concurrent sessions."""
    
    _instance: Optional['SessionManager'] = None
    
    def __init__(self, max_sessions: int = 9):
        self.max_sessions = max_sessions
        self.sessions: Dict[int, SessionInfo] = {}
        self.active_session_id: Optional[int] = None
        self._next_id = 1
    
    @classmethod
    def initialize_instance(cls, max_sessions: int = 9) -> 'SessionManager':
        """Initialize the singleton instance."""
        if cls._instance is None:
            cls._instance = cls(max_sessions=max_sessions)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'SessionManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def create_session(self) -> int:
        """Create a new session and return its ID."""
        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError(f"Maximum {self.max_sessions} sessions reached")
        
        session_id = self._next_id
        self._next_id += 1
        
        session = SessionInfo(session_id=session_id)
        self.sessions[session_id] = session
        self.active_session_id = session_id
        
        logger.info(f"Created session {session_id}")
        return session_id
    
    def get_session(self, session_id: Optional[int] = None) -> Optional[SessionInfo]:
        """Get a session by ID, or the active session if ID is None."""
        if session_id is None:
            session_id = self.active_session_id
        return self.sessions.get(session_id)
    
    def switch_session(self, session_id: int) -> bool:
        """Switch to a different session."""
        if session_id in self.sessions:
            self.active_session_id = session_id
            logger.info(f"Switched to session {session_id}")
            return True
        return False
    
    def get_active_session(self) -> Optional[SessionInfo]:
        """Get the currently active session."""
        return self.get_session(self.active_session_id)
    
    async def cancel_session(self, session_id: Optional[int] = None) -> bool:
        """Cancel a specific session or the active one."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        if session.task and not session.task.done():
            logger.info(f"Cancelling session {session.session_id}")
            session.task.cancel()
            try:
                await asyncio.wait_for(session.task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            session.status = SessionStatus.CANCELLED
            session.completed_at = datetime.now()
            return True
        
        return False
    
    async def stop_session(self, session_id: Optional[int] = None) -> bool:
        """Alias for cancel_session - stop a specific session or the active one."""
        return await self.cancel_session(session_id)
    
    async def cancel_all_sessions(self) -> int:
        """Cancel all active sessions."""
        count = 0
        for session_id in list(self.sessions.keys()):
            if await self.cancel_session(session_id):
                count += 1
        logger.info(f"Cancelled {count} sessions")
        return count
    
    def remove_session(self, session_id: int) -> bool:
        """Remove a session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Can't remove session with active task
            if session.task and not session.task.done():
                logger.warning(f"Cannot remove session {session_id} - task is still running")
                return False
            
            del self.sessions[session_id]
            
            # Switch to another session or create a new one
            if self.active_session_id == session_id:
                if self.sessions:
                    # Switch to the first available session
                    self.active_session_id = next(iter(self.sessions.keys()))
                else:
                    # No sessions left
                    self.active_session_id = None
                    
            logger.info(f"Removed session {session_id}")
            return True
        return False
    
    def list_sessions(self) -> List[SessionInfo]:
        """List all sessions."""
        return list(self.sessions.values())
    
    def get_session_count(self) -> int:
        """Get the number of sessions."""
        return len(self.sessions)
    
    def get_active_sessions(self) -> List[SessionInfo]:
        """Get all sessions that are currently running."""
        return [
            session for session in self.sessions.values()
            if session.status in [SessionStatus.PLANNING, SessionStatus.EXECUTING]
        ]
