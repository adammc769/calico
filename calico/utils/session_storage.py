"""Session-based storage management for photos, logs, and training data."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class SessionStorage:
    """Manages session-based file storage for screenshots, logs, and training data."""

    _WINDOWS_ILLEGAL_CHARS = r'<>:"/\\|?*'
    _WINDOWS_ILLEGAL_RE = re.compile(rf"[{re.escape(_WINDOWS_ILLEGAL_CHARS)}\x00-\x1F]")

    @classmethod
    def _sanitize_path_segment(cls, value: str) -> str:
        sanitized = cls._WINDOWS_ILLEGAL_RE.sub("_", value)
        sanitized = sanitized.rstrip(" .")
        sanitized = sanitized.strip()
        return sanitized or "session"
    
    def __init__(self, session_id: Optional[str] = None, base_dir: str = "./sessions"):
        """
        Initialize session storage.
        
        Args:
            session_id: UUID for the session. If None, generates a new one.
            base_dir: Base directory for all sessions (default: ./sessions)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self._fs_session_id = self._sanitize_path_segment(self.session_id)
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / self._fs_session_id
        
        # Create session subdirectories
        self.photos_dir = self.session_dir / "photos"
        self.logs_dir = self.session_dir / "logs"
        self.data_dir = self.session_dir / "data"
        self.captcha_dir = self.session_dir / "captcha"
        self.dom_dir = self.session_dir / "dom_snapshots"
        
        self._ensure_directories()
        
        # Session metadata
        self.metadata_file = self.session_dir / "metadata.json"
        self._init_metadata()
        
        # Track URLs for which we've already saved DOM snapshots
        self._dom_snapshot_urls: set = set()
    
    def _ensure_directories(self) -> None:
        """Create session directory structure if it doesn't exist."""
        for directory in [self.photos_dir, self.logs_dir, self.data_dir, self.captcha_dir, self.dom_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    def _init_metadata(self) -> None:
        """Initialize or load session metadata."""
        if not self.metadata_file.exists():
            metadata = {
                "session_id": self.session_id,
                "created_at": datetime.utcnow().isoformat(),
                "screenshots": [],
                "logs": [],
                "actions": [],
                "dom_snapshots": []
            }
            self._save_metadata(metadata)
        else:
            logger.debug(f"Loading existing metadata for session {self.session_id}")
            # Load existing DOM snapshot URLs
            metadata = self._load_metadata()
            for snapshot in metadata.get("dom_snapshots", []):
                self._dom_snapshot_urls.add(snapshot.get("url", ""))
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save metadata to file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def save_screenshot(self, image_data: bytes, name: Optional[str] = None, 
                       action_context: Optional[Dict[str, Any]] = None) -> Path:
        """
        Save a screenshot to the session photos directory.
        
        Args:
            image_data: Raw image bytes
            name: Optional name for the screenshot. If None, generates timestamp-based name
            action_context: Optional context about the action that triggered the screenshot
            
        Returns:
            Path to the saved screenshot
        """
        if name is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            name = f"screenshot_{timestamp}.png"
        
        if not name.endswith('.png'):
            name += '.png'
        
        screenshot_path = self.photos_dir / name
        
        with open(screenshot_path, 'wb') as f:
            f.write(image_data)
        
        # Update metadata
        metadata = self._load_metadata()
        screenshot_entry = {
            "filename": name,
            "path": str(screenshot_path.relative_to(self.base_dir)),
            "timestamp": datetime.utcnow().isoformat(),
            "size_bytes": len(image_data)
        }
        if action_context:
            screenshot_entry["context"] = action_context
        
        metadata.setdefault("screenshots", []).append(screenshot_entry)
        self._save_metadata(metadata)
        
        logger.info(f"Saved screenshot: {screenshot_path}")
        return screenshot_path
    
    def save_log(self, content: str, log_type: str = "action", 
                 level: str = "INFO") -> Path:
        """
        Save a log entry to the session logs directory.
        
        Args:
            content: Log content
            log_type: Type of log (action, error, gpt, playwright, etc.)
            level: Log level (INFO, ERROR, DEBUG, etc.)
            
        Returns:
            Path to the log file
        """
        log_file = self.logs_dir / f"{log_type}.log"
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level}] {content}\n"
        
        with open(log_file, 'a') as f:
            f.write(log_entry)
        
        # Update metadata
        metadata = self._load_metadata()
        log_entry_meta = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": log_type,
            "level": level,
            "file": str(log_file.relative_to(self.base_dir))
        }
        metadata.setdefault("logs", []).append(log_entry_meta)
        self._save_metadata(metadata)
        
        return log_file
    
    def save_action_data(self, action: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Save action execution data for training purposes.
        
        Args:
            action: Action that was executed
            result: Result of the action execution
        """
        metadata = self._load_metadata()
        action_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "result": result
        }
        metadata.setdefault("actions", []).append(action_entry)
        self._save_metadata(metadata)
        
        # Also save to a separate actions file for easier analysis
        actions_file = self.data_dir / "actions.jsonl"
        with open(actions_file, 'a') as f:
            f.write(json.dumps(action_entry) + '\n')
    
    def save_training_data(self, data: Dict[str, Any], data_type: str = "general") -> Path:
        """
        Save training data to the session data directory.
        
        Args:
            data: Training data to save
            data_type: Type of training data (general, gpt_interaction, dom_data, etc.)
            
        Returns:
            Path to the saved data file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        data_file = self.data_dir / f"{data_type}_{timestamp}.json"
        
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved training data: {data_file}")
        return data_file
    
    def save_captcha(self, screenshot_data: bytes, captcha_type: str, url: str, 
                     html_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Save captcha screenshot and information.
        
        Args:
            screenshot_data: Screenshot bytes of the captcha
            captcha_type: Type of captcha (e.g., 'recaptcha', 'hcaptcha', 'cloudflare')
            url: URL where captcha was encountered
            html_content: Optional HTML content for debugging
            
        Returns:
            Dictionary with captcha information including captcha_id and paths
        """
        captcha_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Save screenshot
        screenshot_name = f"{timestamp}_{captcha_id}_{captcha_type}.png"
        screenshot_path = self.captcha_dir / screenshot_name
        
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_data)
        
        # Save HTML content if provided
        html_path = None
        if html_content:
            html_name = f"{timestamp}_{captcha_id}_{captcha_type}.html"
            html_path = self.captcha_dir / html_name
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        # Save captcha metadata
        captcha_info = {
            "captcha_id": captcha_id,
            "timestamp": timestamp,
            "type": captcha_type,
            "url": url,
            "screenshot_path": str(screenshot_path),
            "html_path": str(html_path) if html_path else None,
            "solved": False,
            "api_url": f"/api/captcha/{self.session_id}/{captcha_id}"
        }
        
        # Save to JSON file for easy access
        captcha_json_path = self.captcha_dir / f"{captcha_id}.json"
        with open(captcha_json_path, 'w') as f:
            json.dump(captcha_info, f, indent=2)
        
        # Update session metadata
        metadata = self._load_metadata()
        if "captchas" not in metadata:
            metadata["captchas"] = []
        metadata["captchas"].append(captcha_info)
        self._save_metadata(metadata)
        
        logger.info(f"Captcha saved: {captcha_id} ({captcha_type}) at {url}")
        
        return captcha_info
    
    def mark_captcha_solved(self, captcha_id: str, solution: Optional[str] = None) -> bool:
        """
        Mark a captcha as solved.
        
        Args:
            captcha_id: The captcha identifier
            solution: Optional solution data
            
        Returns:
            True if captcha was found and marked, False otherwise
        """
        captcha_json_path = self.captcha_dir / f"{captcha_id}.json"
        
        if not captcha_json_path.exists():
            logger.warning(f"Captcha {captcha_id} not found")
            return False
        
        # Load captcha info
        with open(captcha_json_path, 'r') as f:
            captcha_info = json.load(f)
        
        # Mark as solved
        captcha_info["solved"] = True
        captcha_info["solved_at"] = datetime.utcnow().isoformat()
        if solution:
            captcha_info["solution"] = solution
        
        # Save updated info
        with open(captcha_json_path, 'w') as f:
            json.dump(captcha_info, f, indent=2)
        
        # Update session metadata
        metadata = self._load_metadata()
        if "captchas" in metadata:
            for i, c in enumerate(metadata["captchas"]):
                if c.get("captcha_id") == captcha_id:
                    metadata["captchas"][i] = captcha_info
                    break
        self._save_metadata(metadata)
        
        logger.info(f"Captcha {captcha_id} marked as solved")
        return True
    
    def get_captcha(self, captcha_id: str) -> Optional[Dict[str, Any]]:
        """
        Get captcha information by ID.
        
        Args:
            captcha_id: The captcha identifier
            
        Returns:
            Captcha information dictionary or None if not found
        """
        captcha_json_path = self.captcha_dir / f"{captcha_id}.json"
        
        if not captcha_json_path.exists():
            return None
        
        with open(captcha_json_path, 'r') as f:
            return json.load(f)
    
    def list_captchas(self, unsolved_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all captchas for this session.
        
        Args:
            unsolved_only: If True, only return unsolved captchas
            
        Returns:
            List of captcha information dictionaries
        """
        captchas = []
        
        for captcha_file in self.captcha_dir.glob("*.json"):
            with open(captcha_file, 'r') as f:
                captcha_info = json.load(f)
            
            if unsolved_only and captcha_info.get("solved", False):
                continue
            
            captchas.append(captcha_info)
        
        return sorted(captchas, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def save_dom_snapshot(self, html_content: str, url: str, 
                          action_context: Optional[Dict[str, Any]] = None,
                          force: bool = False) -> Optional[Path]:
        """
        Save a DOM snapshot for a failed page interaction.
        Only saves one snapshot per unique URL unless force=True.
        
        Args:
            html_content: HTML content of the page
            url: URL of the page
            action_context: Optional context about the action that failed
            force: If True, saves even if we've already saved this URL
            
        Returns:
            Path to the saved snapshot or None if already saved
        """
        # Check if we've already saved a snapshot for this URL
        if not force and url in self._dom_snapshot_urls:
            logger.debug(f"DOM snapshot for {url} already saved, skipping")
            return None
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # Create a safe filename from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        safe_domain = parsed.netloc.replace(".", "_").replace(":", "_")
        safe_path = parsed.path.replace("/", "_").replace(".", "_")[:50]  # Limit length
        
        filename = f"dom_{timestamp}_{safe_domain}{safe_path}.html"
        snapshot_path = self.dom_dir / filename
        
        # Save HTML content
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Mark this URL as saved
        self._dom_snapshot_urls.add(url)
        
        # Update metadata
        metadata = self._load_metadata()
        snapshot_entry = {
            "filename": filename,
            "path": str(snapshot_path.relative_to(self.base_dir)),
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "size_bytes": len(html_content.encode('utf-8'))
        }
        if action_context:
            snapshot_entry["context"] = action_context
        
        metadata.setdefault("dom_snapshots", []).append(snapshot_entry)
        self._save_metadata(metadata)
        
        logger.info(f"Saved DOM snapshot: {snapshot_path}")
        return snapshot_path
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the session including all artifacts."""
        metadata = self._load_metadata()
        
        return {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "created_at": metadata.get("created_at"),
            "screenshots_count": len(metadata.get("screenshots", [])),
            "logs_count": len(metadata.get("logs", [])),
            "actions_count": len(metadata.get("actions", [])),
            "captchas_count": len(metadata.get("captchas", [])),
            "dom_snapshots_count": len(metadata.get("dom_snapshots", [])),
            "photos_dir": str(self.photos_dir),
            "logs_dir": str(self.logs_dir),
            "data_dir": str(self.data_dir),
            "captcha_dir": str(self.captcha_dir),
            "dom_dir": str(self.dom_dir)
        }
    
    @classmethod
    def list_sessions(cls, base_dir: str = "./sessions") -> list[Dict[str, Any]]:
        """
        List all available sessions.
        
        Args:
            base_dir: Base directory containing sessions
            
        Returns:
            List of session summaries
        """
        sessions_path = Path(base_dir)
        if not sessions_path.exists():
            return []
        
        sessions = []
        for session_dir in sessions_path.iterdir():
            if session_dir.is_dir() and not session_dir.name.startswith('.'):
                metadata_file = session_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    sessions.append({
                        "session_id": metadata.get("session_id", session_dir.name),
                        "created_at": metadata.get("created_at"),
                        "path": str(session_dir)
                    })
        
        return sorted(sessions, key=lambda x: x.get("created_at", ""), reverse=True)
