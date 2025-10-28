"""WebSocket Routes for Trading Dashboard."""

from fastapi import APIRouter, HTTPException, WebSocket
from ..models import SubscriptionRequest
from ..web_components import app_state

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
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    await app_state.websocket_handlers.websocket_endpoint(websocket)

# WebSocket subscription routes
@router.get("/api/websocket/subscriptions")
async def get_subscriptions():
    """Get current WebSocket subscriptions."""
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_subscriptions()

@router.post("/api/websocket/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest):
    """Subscribe to a WebSocket channel."""
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.subscribe_to_channel(request.dict())

@router.post("/api/websocket/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest):
    """Unsubscribe from a WebSocket channel."""
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.unsubscribe_from_channel(request.dict())

@router.get("/api/websocket/status")
async def get_realtime_status():
    """Get real-time data status."""
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_realtime_status()

@router.post("/api/websocket/toggle")
async def toggle_realtime_data():
    """Toggle real-time data streaming."""
    check_handlers_ready("websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.toggle_realtime_data()
