"""WebSocket Routes for Trading Dashboard."""

import logging
from fastapi import APIRouter, HTTPException, WebSocket
from ..models import SubscriptionRequest
from ..web_components import app_state

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    try:
        # Accept the WebSocket connection immediately to avoid 403 errors
        await websocket.accept()

        # Check if app_state is initialized after accepting
        if app_state is None:
            await websocket.close(code=1013, reason="Service unavailable - application not initialized")
            return

        # Check if websocket_handlers are initialized (using websocket close instead of HTTPException)
        if app_state.websocket_handlers is None:
            await websocket.close(code=1013, reason="Server not ready - websocket_handlers not initialized")
            return

        await app_state.websocket_handlers.websocket_endpoint(websocket)
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=1013, reason="WebSocket initialization error")
        except:
            pass

# WebSocket subscription routes
@router.get("/api/websocket/subscriptions")
async def get_subscriptions():
    """Get current WebSocket subscriptions."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_subscriptions()

@router.post("/api/websocket/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest):
    """Subscribe to a WebSocket channel."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.subscribe_to_channel(request.dict())

@router.post("/api/websocket/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest):
    """Unsubscribe from a WebSocket channel."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.unsubscribe_from_channel(request.dict())

@router.get("/api/websocket/status")
async def get_realtime_status():
    """Get real-time data status."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_realtime_status()

@router.post("/api/websocket/toggle")
async def toggle_realtime_data():
    """Toggle real-time data streaming."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.toggle_realtime_data()
