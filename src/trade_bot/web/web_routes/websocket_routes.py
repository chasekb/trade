"""WebSocket Routes for Trading Dashboard."""

from fastapi import APIRouter, HTTPException, WebSocket
from ..models import SubscriptionRequest
from ..web_handlers import WebSocketHandlers

# Create router
router = APIRouter()

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, websocket_handlers: WebSocketHandlers = None):
    """Handle WebSocket connections."""
    if websocket_handlers is None:
        await websocket.close(code=1011, reason="Server not ready")
        return
    await websocket_handlers.websocket_endpoint(websocket)

# WebSocket subscription routes
@router.get("/api/websocket/subscriptions")
async def get_subscriptions(websocket_handlers: WebSocketHandlers = None):
    """Get current WebSocket subscriptions."""
    if websocket_handlers is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_subscriptions()

@router.post("/api/websocket/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest, websocket_handlers: WebSocketHandlers = None):
    """Subscribe to a WebSocket channel."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.subscribe_to_channel(request.dict())

@router.post("/api/websocket/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest, websocket_handlers: WebSocketHandlers = None):
    """Unsubscribe from a WebSocket channel."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.unsubscribe_from_channel(request.dict())

@router.get("/api/websocket/status")
async def get_realtime_status(websocket_handlers: WebSocketHandlers = None):
    """Get real-time data status."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_realtime_status()

@router.post("/api/websocket/toggle")
async def toggle_realtime_data(websocket_handlers: WebSocketHandlers = None):
    """Toggle real-time data streaming."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.toggle_realtime_data()
