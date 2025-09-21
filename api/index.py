"""
Vercel serverless function entry point for the trading bot web dashboard.
This adapts the FastAPI application for Vercel's serverless environment.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Import the web server app
from trade_bot.web_server import app

# Create a new FastAPI instance for Vercel
vercel_app = FastAPI(title="Trading Bot API", version="1.0.0")

# Mount static files
vercel_app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include all routes from the original app
vercel_app.include_router(app.router)

# Root endpoint
@vercel_app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse("dashboard_enhanced.html", {"request": request})

# Health check endpoint
@vercel_app.get("/health")
async def health_check():
    """Health check endpoint for Vercel."""
    return {"status": "healthy", "service": "trading-bot"}

# Handler for Vercel
def handler(request):
    """Vercel serverless function handler."""
    return vercel_app(request.scope, request.receive, request.send)

# For local development
if __name__ == "__main__":
    uvicorn.run(vercel_app, host="0.0.0.0", port=8000)

