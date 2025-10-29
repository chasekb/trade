# Archived Components

This directory contains code components that have been archived as they are no longer used in the current docker-compose deployment.

## Archived: Vanilla JavaScript Dashboard

**Archived on:** October 29, 2025

**Reason:** Transitioned to React/TypeScript frontend deployed via docker-compose

The archived components include:

### Archived Directories:
- `vanilla_js_dashboard/static/` - All vanilla JavaScript, CSS, and HTML dashboard files
- `vanilla_js_dashboard/templates/` - HTML templates for the vanilla dashboard
- `vanilla_js_dashboard/scripts/` - CLI scripts including web dashboard runner and various utilities
- `vanilla_js_dashboard/main.py` - Main CLI entry point for running the vanilla JS web dashboard

### What was archived:
1. **Vanilla JavaScript Dashboard Implementation** (`static/js/`):
   - `dashboard_enhanced_modular.js` - Main modular dashboard controller
   - `dashboard_enhanced.js` - Enhanced dashboard
   - `dashboard.js` - Basic dashboard
   - `modules/` - Various dashboard modules (TradingStats, LiveTrading, ML analytics, etc.)

2. **HTML Files** (`templates/`):
   - `dashboard_enhanced_modular.html`
   - `dashboard_enhanced.html`
   - `dashboard.html`
   - `ml_dashboard.html`

3. **CSS Styles** (`static/css/`):
   - `dashboard-optimized.css`

4. **CLI Tools** (`scripts/web/`):
   - `web_dashboard.py` - Web server wrapper script

5. **Main Entry Point** (`main.py`):
   - CLI interface for running different components including the web dashboard

### Current Deployment:
The project now uses:
- **Frontend:** React/TypeScript Next.js application in `frontend/` directory
- **Backend:** Python FastAPI server (`app.py`)
- **Deployment:** Docker Compose with separate frontend and backend services

### Restoring Archived Code:
If you need to restore the vanilla JavaScript dashboard:
1. Move files back from `archive/vanilla_js_dashboard/` to their original locations
2. Run `python main.py web` to start the vanilla JavaScript web dashboard
3. Access at `http://localhost:8000`

**Note:** The archived code is preserved for historical reference but is not actively maintained or tested.
