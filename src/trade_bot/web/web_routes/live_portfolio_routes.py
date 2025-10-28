"""Live Portfolio Routes for Trading Dashboard."""

from fastapi import APIRouter, HTTPException
from ..web_handlers.live_portfolio_handlers import LivePortfolioHandlers

# Create router
router = APIRouter()

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# Live portfolio routes
@router.get("/api/live-portfolio/status")
async def get_live_portfolio_status(live_portfolio_handlers: LivePortfolioHandlers = None):
    """Get live portfolio status from Coinbase API."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_live_portfolio_status()

@router.get("/api/live-portfolio/summary")
async def get_live_portfolio_summary(live_portfolio_handlers: LivePortfolioHandlers = None):
    """Get live portfolio summary formatted for frontend."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_portfolio_summary_for_frontend()

@router.get("/api/live-portfolio/accounts")
async def get_live_portfolio_accounts(account_uuid: str = None, live_portfolio_handlers: LivePortfolioHandlers = None):
    """Get live portfolio account details."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_account_details(account_uuid)
