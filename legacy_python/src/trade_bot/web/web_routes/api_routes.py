"""API Routes for Trading Dashboard."""

import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response

from ..web_components import RateLimiter, app_state, get_app_state

# Create router
router = APIRouter()

# Global rate limiter instance
rate_limiter = RateLimiter()

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# Main dashboard routes
@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the main dashboard page (modular by default, flaggable)."""
    # Feature flag to toggle modular dashboard
    use_modular = os.getenv('USE_MODULAR', 'true').lower() in ('1', 'true', 'yes', 'on')

    if use_modular:
        return FileResponse("static/dashboard_enhanced_modular.html")
    else:
        app_state = get_app_state()
        check_handlers_ready("app_state.dashboard_handlers", app_state.dashboard_handlers)
        return await app_state.dashboard_handlers.get_dashboard(request)

@router.get("/modular", response_class=HTMLResponse)
async def get_modular_dashboard():
    """Serve the modular dashboard page with caching headers."""
    import time
    response = FileResponse(
        "static/dashboard_enhanced_modular.html",
        media_type="text/html",
        headers={
            "Cache-Control": "public, max-age=300",  # 5 minutes
            "ETag": f"modular-{int(time.time())}",
            "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
    )
    return response

@router.get("/modular-dashboard", response_class=HTMLResponse)
async def get_modular_dashboard_alt():
    """Serve the modular dashboard page (alternative route)."""
    return FileResponse("static/dashboard_enhanced_modular.html")

@router.get("/legacy", response_class=HTMLResponse)
async def get_legacy_dashboard(request: Request):
    """Serve the legacy enhanced dashboard page."""
    app_state = get_app_state()
    check_handlers_ready("app_state.dashboard_handlers", app_state.dashboard_handlers)
    return await app_state.dashboard_handlers.get_dashboard(request)

@router.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    return Response(content="", media_type="image/x-icon")

# General API routes
@router.get("/api/real-time-data")
async def get_real_time_data(product_id: str = None):
    """Get real-time market data."""
    app_state = get_app_state()
    check_handlers_ready("app_state.dashboard_handlers", app_state.dashboard_handlers)
    return await app_state.dashboard_handlers.get_real_time_data(product_id)

@router.get("/api/historical-data")
async def get_historical_data(product_id: str, start_time: str = None, end_time: str = None, granularity: int = 3600, days: int = 7):
    """Get historical market data."""
    app_state = get_app_state()
    check_handlers_ready("app_state.dashboard_handlers", app_state.dashboard_handlers)

    # If start_time and end_time are not provided, calculate from days
    if start_time is None or end_time is None:
        from datetime import datetime, timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        start_time = start_time.isoformat()
        end_time = end_time.isoformat()

    return await app_state.dashboard_handlers.get_historical_data(product_id, start_time, end_time, granularity)

# Symbol and product data routes
@router.get("/api/symbols")
async def get_available_symbols():
    """Get available trading symbols."""
    app_state = get_app_state()
    check_handlers_ready("app_state.api_handlers", app_state.api_handlers)
    return await app_state.api_handlers.get_available_symbols()

@router.get("/api/products")
async def get_available_products():
    """Get available products for trading."""
    app_state = get_app_state()
    check_handlers_ready("app_state.api_handlers", app_state.api_handlers)
    return await app_state.api_handlers.get_available_products()

@router.get("/api/channels")
async def get_available_channels():
    """Get available WebSocket channels."""
    app_state = get_app_state()
    check_handlers_ready("app_state.api_handlers", app_state.api_handlers)
    return await app_state.api_handlers.get_available_channels()

# Health check
@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    app_state = get_app_state()
    check_handlers_ready("app_state.api_handlers", app_state.api_handlers)
    return await app_state.api_handlers.health_check()

# Additional API endpoints
@router.get("/api/subscriptions")
async def get_subscriptions_alt():
    """Alternative endpoint for subscriptions."""
    app_state = get_app_state()
    check_handlers_ready("app_state.websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_subscriptions()

@router.get("/api/realtime-status")
async def get_realtime_status_alt():
    """Alternative endpoint for realtime status."""
    app_state = get_app_state()
    check_handlers_ready("app_state.websocket_handlers", app_state.websocket_handlers)
    return await app_state.websocket_handlers.get_realtime_status()

@router.get("/api/data-summary")
async def get_data_summary_alt():
    """Alternative endpoint for data summary statistics."""
    app_state = get_app_state()
    check_handlers_ready("app_state.dashboard_handlers", app_state.dashboard_handlers)
    return await app_state.dashboard_handlers.get_data_summary()

@router.post("/api/log")
async def log_message(request: Request):
    """Log a message from the frontend."""
    try:
        data = await request.json()
        message = data.get("message")
        if message:
            print(f"Frontend log: {message}")
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=400, detail="Missing 'message' in request body")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
