"""ML-specific routes for the web dashboard."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

# Create main router for ML dashboard pages
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/ml-dashboard", response_class=HTMLResponse)
async def get_ml_dashboard(request: Request):
    """Serve the ML monitoring dashboard page."""
    try:
        return templates.TemplateResponse("ml_dashboard.html", {"request": request})
    except Exception as e:
        # If template doesn't exist or other error, return basic error page
        return HTMLResponse(content=f"""
        <html>
            <head><title>ML Dashboard Error</title></head>
            <body>
                <h1>ML Dashboard Not Available</h1>
                <p>Error loading ML dashboard: {str(e)}</p>
                <p>Make sure the ml_dashboard.html template exists and the ML system is properly configured.</p>
            </body>
        </html>
        """, status_code=500)


@router.get("/ml-analytics", response_class=HTMLResponse)
async def get_ml_analytics(request: Request):
    """Serve the ML analytics dashboard (alias for backward compatibility)."""
    return await get_ml_dashboard(request)
