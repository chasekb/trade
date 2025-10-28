"""Web server components package."""

from .rate_limiter import RateLimiter
from .websocket_manager import WebSocketManager
from .application_state import ApplicationState

# Export ApplicationState as app_state for backward compatibility
# This will be set during application initialization
app_state = None

def get_app_state():
    """Get the current application state."""
    if app_state is None:
        raise RuntimeError("Application state not initialized. Make sure startup_event has completed.")
    return app_state

def set_app_state(state):
    """Set the application state."""
    global app_state
    app_state = state

__all__ = [
    'RateLimiter',
    'WebSocketManager',
    'ApplicationState',
    'app_state',
    'get_app_state',
    'set_app_state'
]
