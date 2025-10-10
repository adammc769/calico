"""FastAPI server for Chrome extension communication."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from calico.workflow.orchestrator import run_agent_session, AgentRunError
from calico.workflow.config import get_settings
from calico.workflow.backends import get_backend_registry

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Calico Backend API",
    description="API server for Chrome extension communication",
    version="1.0.0"
)

# Configure CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extension origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []


class PromptRequest(BaseModel):
    """Request model for agent prompts."""
    prompt: str
    profileId: Optional[str] = None
    sessionId: Optional[str] = None
    domCandidates: Optional[List[Dict[str, Any]]] = None
    ocrChunks: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None


class ProfileRequest(BaseModel):
    """Request model for profile operations."""
    profile: Dict[str, Any]


class TaskUpdateModel(BaseModel):
    """Model for task updates."""
    sessionId: str
    status: Optional[str] = None
    name: Optional[str] = None
    profileId: Optional[str] = None
    logs: Optional[List[str]] = None


class CaptchaSolutionRequest(BaseModel):
    """Request model for submitting captcha solutions."""
    solution: str


# HTTP Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    registry = get_backend_registry()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backend_mode": settings.backend_mode,
        "available_backends": list(registry.get_available_backends().keys())
    }


@app.post("/agent/prompt")
async def submit_prompt(request: PromptRequest):
    """Submit a prompt for agent execution with proper candidate-based flow."""
    try:
        logger.info(f"Received prompt request for session {request.sessionId}")
        
        # STEP 1: Navigate and extract DOM candidates (lightweight)
        context = request.context or {}
        
        # STEP 2: If domCandidates provided, use candidate-based flow
        if request.domCandidates:
            logger.info(f"Using provided DOM candidates ({len(request.domCandidates)} candidates)")
            context["dom_candidates"] = request.domCandidates[:10]  # Limit to top 10
        else:
            logger.info("No DOM candidates provided, will extract during navigation")
            
        # STEP 3: Add OCR chunks if available  
        if request.ocrChunks:
            logger.info(f"Adding OCR chunks ({len(request.ocrChunks)} chunks)")
            context["ocr_chunks"] = request.ocrChunks[:5]  # Limit OCR chunks
        
        # STEP 4: Create lightweight context (no massive DOM data)
        lightweight_context = {
            "session_id": request.sessionId,
            "use_candidate_flow": True,  # Signal to use candidate-based approach
            "max_dom_tokens": 5000,  # Strict token limit for DOM data
            "max_candidates": 10,     # Maximum candidates to analyze
            **context
        }
        
        # Use orchestrator with candidate-based flow
        result = run_agent_session(
            agent_name=request.profileId or "default",
            goal=request.prompt,
            context=lightweight_context,
            llm_config={"max_tokens": 25000}  # Stay well under 30k limit
        )
        
        # Notify WebSocket clients about task completion
        await broadcast_task_update({
            "sessionId": request.sessionId or f"session-{result.run_id}",
            "status": "completed" if result.completed else "failed",
            "name": request.prompt[:50] + "..." if len(request.prompt) > 50 else request.prompt,
            "profileId": request.profileId
        })
        
        return {
            "success": result.completed,
            "runId": result.run_id,
            "status": result.status,
            "data": result.data,
            "task": {
                "sessionId": request.sessionId or f"session-{result.run_id}",
                "status": "completed" if result.completed else "failed",
                "name": request.prompt[:50] + "..." if len(request.prompt) > 50 else request.prompt
            },
            "logs": [f"Task {result.status}"]
        }
        
    except AgentRunError as exc:
        logger.error(f"Agent run error: {exc}")
        raise HTTPException(status_code=500, detail={
            "error": "Agent execution failed", 
            "message": str(exc),
            "runId": exc.result.run_id if hasattr(exc, 'result') else None
        })
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail={
            "error": "Internal server error",
            "message": str(exc)
        })


@app.get("/profiles")
async def list_profiles():
    """List available profiles."""
    try:
        # For now, return hardcoded profiles until MCP backend is fully integrated
        return {"profiles": [{"id": "default", "name": "Default Profile"}]}
    except Exception as exc:
        logger.error(f"Failed to list profiles: {exc}")
        raise HTTPException(status_code=500, detail={
            "error": "Failed to list profiles",
            "message": str(exc)
        })


@app.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    """Get a specific profile."""
    try:
        # For now, return hardcoded profile until MCP backend is fully integrated
        if profile_id == "default":
            return {"profile": {
                "id": "default",
                "displayName": "Default Profile",
                "persona": "A helpful assistant that can navigate websites and perform tasks",
                "source": "builtin"
            }}
        else:
            raise HTTPException(status_code=404, detail={"error": "Profile not found"})
    except Exception as exc:
        logger.error(f"Failed to get profile {profile_id}: {exc}")
        raise HTTPException(status_code=404, detail={
            "error": "Profile not found",
            "message": str(exc)
        })


@app.post("/profiles")
async def upsert_profile(request: ProfileRequest):
    """Create or update a profile."""
    try:
        # For now, return the profile as-is until MCP backend is fully integrated
        profile_data = request.profile
        if "id" not in profile_data:
            profile_data["id"] = "custom-profile"
        if "displayName" not in profile_data:
            profile_data["displayName"] = profile_data.get("id", "Custom Profile")
        return {"profile": profile_data}
    except Exception as exc:
        logger.error(f"Failed to upsert profile: {exc}")
        raise HTTPException(status_code=500, detail={
            "error": "Failed to save profile",
            "message": str(exc)
        })


@app.get("/backend/info")
async def backend_info():
    """Get backend information."""
    registry = get_backend_registry()
    settings = get_settings()
    
    return {
        "currentBackend": settings.backend_mode,
        "availableBackends": {
            name: {
                "name": info.name,
                "description": info.description,
                "requirements": info.requirements,
                "available": info.is_available
            }
            for name, info in registry.list_backends().items()
        },
        "settings": {
            "mcpUrl": settings.mcp_ws_url,
            "requestTimeout": settings.mcp_request_timeout_seconds
        }
    }


# Captcha Management Endpoints

@app.get("/api/captcha/{session_id}")
async def list_session_captchas(session_id: str):
    """List all captchas for a session."""
    try:
        from calico.utils.session_storage import SessionStorage
        storage = SessionStorage(session_id=session_id)
        
        pending_captchas = storage.get_pending_captchas()
        
        return {
            "session_id": session_id,
            "captchas": pending_captchas,
            "count": len(pending_captchas)
        }
    except Exception as e:
        logger.error(f"Error listing captchas for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/captcha/{session_id}/{captcha_id}")
async def get_captcha_details(session_id: str, captcha_id: str):
    """Get details and status of a specific captcha."""
    try:
        from calico.utils.session_storage import SessionStorage
        storage = SessionStorage(session_id=session_id)
        
        # Load metadata
        metadata = storage._load_metadata()
        captchas = metadata.get("captchas", [])
        
        captcha = next((c for c in captchas if c.get("captcha_id") == captcha_id), None)
        
        if not captcha:
            raise HTTPException(status_code=404, detail="Captcha not found")
        
        return captcha
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting captcha {captcha_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/captcha/{session_id}/{captcha_id}/image")
async def get_captcha_image(session_id: str, captcha_id: str):
    """Get the captcha screenshot image."""
    try:
        sessions_dir = Path("./sessions")
        image_path = sessions_dir / session_id / "captcha" / f"{captcha_id}.png"
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Captcha image not found")
        
        return FileResponse(
            image_path,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename={captcha_id}.png"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving captcha image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/captcha/{session_id}/{captcha_id}/solve")
async def submit_captcha_solution(session_id: str, captcha_id: str, solution: CaptchaSolutionRequest):
    """Submit a solution for a captcha."""
    try:
        from calico.utils.session_storage import SessionStorage
        storage = SessionStorage(session_id=session_id)
        
        success = storage.update_captcha_solution(captcha_id, solution.solution)
        
        if not success:
            raise HTTPException(status_code=404, detail="Captcha not found")
        
        # Broadcast to WebSocket clients that captcha was solved
        await broadcast_captcha_solved(session_id, captcha_id, solution.solution)
        
        return {
            "success": True,
            "captcha_id": captcha_id,
            "message": "Captcha solution submitted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting captcha solution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for real-time updates

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        logger.info("Chrome extension connected via WebSocket")
        
        # Send initial status
        await websocket.send_json({
            "type": "connection_established",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_json()
                await handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                break
                
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info("Chrome extension disconnected from WebSocket")


async def handle_websocket_message(websocket: WebSocket, data: Dict[str, Any]):
    """Handle incoming WebSocket messages."""
    message_type = data.get("type")
    
    if message_type == "ping":
        await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
    
    elif message_type == "subscribe_session":
        session_id = data.get("sessionId")
        # Subscribe to session updates (implementation depends on requirements)
        await websocket.send_json({
            "type": "session_subscribed",
            "sessionId": session_id
        })
    
    else:
        logger.warning(f"Unknown WebSocket message type: {message_type}")


async def broadcast_task_update(task_data: Dict[str, Any]):
    """Broadcast task updates to all connected WebSocket clients."""
    if not active_connections:
        return
    
    message = {
        "type": "task_update",
        "task": task_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)


async def broadcast_log(session_id: str, message: str, level: str = "info"):
    """Broadcast log messages to WebSocket clients."""
    if not active_connections:
        return
    
    log_message = {
        "type": "log",
        "sessionId": session_id,
        "level": level,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(log_message)
        except Exception:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)


async def broadcast_captcha_solved(session_id: str, captcha_id: str, solution: str):
    """Broadcast captcha solution to WebSocket clients."""
    if not active_connections:
        return
    
    message = {
        "type": "captcha_solved",
        "sessionId": session_id,
        "captchaId": captcha_id,
        "solution": solution,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the API server."""
    uvicorn.run(
        "calico.workflow.api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    settings = get_settings()
    port = int(settings.api_server_port) if hasattr(settings, 'api_server_port') else 8000
    run_server(port=port, reload=settings.environment == "development")