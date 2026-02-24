"""WebSocket Routes for Trading Dashboard."""

import logging
from fastapi import APIRouter, HTTPException, WebSocket
from ..models import SubscriptionRequest
from ..web_components import get_app_state

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

        # Get current app_state (not the module-level None value)
        try:
            current_app_state = get_app_state()
        except RuntimeError as e:
            await websocket.close(code=1013, reason=f"Service unavailable - {str(e)}")
            return

        # Check if websocket_handlers are initialized (using websocket close instead of HTTPException)
        if current_app_state.websocket_handlers is None:
            # Wait for handlers to initialize (give up to 5 seconds)
            import asyncio
            for _ in range(50):
                if current_app_state.websocket_handlers is not None:
                    break
                await asyncio.sleep(0.1)
            else:
                await websocket.close(code=1013, reason="Server not ready - websocket_handlers not initialized after timeout")
                return

        await current_app_state.websocket_handlers.websocket_endpoint(websocket)
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
    current_app_state = get_app_state()
    check_handlers_ready("websocket_handlers", current_app_state.websocket_handlers)
    return await current_app_state.websocket_handlers.get_subscriptions()

@router.post("/api/websocket/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest):
    """Subscribe to a WebSocket channel."""
    current_app_state = get_app_state()
    check_handlers_ready("websocket_handlers", current_app_state.websocket_handlers)
    return await current_app_state.websocket_handlers.subscribe_to_channel(request.dict())

@router.post("/api/websocket/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest):
    """Unsubscribe from a WebSocket channel."""
    current_app_state = get_app_state()
    check_handlers_ready("websocket_handlers", current_app_state.websocket_handlers)
    return await current_app_state.websocket_handlers.unsubscribe_from_channel(request.dict())

@router.get("/api/websocket/status")
async def get_realtime_status():
    """Get real-time data status."""
    current_app_state = get_app_state()
    check_handlers_ready("websocket_handlers", current_app_state.websocket_handlers)
    return await current_app_state.websocket_handlers.get_realtime_status()

@router.post("/api/websocket/toggle")
async def toggle_realtime_data():
    """Toggle real-time data streaming."""
    current_app_state = get_app_state()
    check_handlers_ready("websocket_handlers", current_app_state.websocket_handlers)
    return await current_app_state.websocket_handlers.toggle_realtime_data()
