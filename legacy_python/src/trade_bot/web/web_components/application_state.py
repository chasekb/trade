from typing import List
"""Application State Management for Web Server.

This module provides a centralized application state class to replace global variables,
making the code more testable, maintainable, and thread-safe.
"""
import asyncio
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field

from ..web_handlers import (
    APIHandlers, DashboardHandlers, BacktestHandlers,
    TradingHandlers, WebSocketHandlers, DataHandlers, LivePortfolioHandlers
)
from ...ml.vector_database_service import VectorDatabaseService
from ...ml.ml_optimizer import MLTradingOptimizer


@dataclass
class TradingState:
    """Trading state data class."""
    is_trading: bool = False
    active_strategy: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    loading_progress: Dict[str, Any] = field(default_factory=lambda: {
        "status": "idle",
        "loaded": 0,
        "total": 0,
        "remaining": 0,
        "progress": 100
    })


class ApplicationState:
    """Centralized application state manager.

    This class replaces the global variables used throughout the web server,
    providing better encapsulation, testability, and thread safety.
    """

    def __init__(self):
        """Initialize the application state."""
        # Core components
        self.data_handler = None
        self.simulated_trading_manager = None
        self.database_manager = None
        self.websocket_client = None

        # WebSocket manager
        self.websocket_manager = None

        # Trading state
        self.trading_state = TradingState()

        # Handlers
        self.api_handlers = None
        self.dashboard_handlers = None
        self.backtest_handlers = None
        self.trading_handlers = None
        self.websocket_handlers = None
        self.data_handlers = None
        self.live_portfolio_handlers = None

        # ML and Vector Database services
        self.vector_db_service = None
        self.ml_optimizer = None

        # Initialization tracking
        self._initialized = False
        self._shutdown = False

    @property
    def initialized(self) -> bool:
        """Check if the application state is fully initialized."""
        return self._initialized

    @property
    def shutdown(self) -> bool:
        """Check if the application is shutting down."""
        return self._shutdown

    def set_initialized(self, value: bool = True):
        """Mark the application as initialized or not."""
        self._initialized = value

    def set_shutdown(self, value: bool = True):
        """Mark the application as shutting down."""
        self._shutdown = value

    def reset_trading_state(self):
        """Reset trading state to defaults."""
        self.trading_state = TradingState()

    def update_loading_progress(self, loaded: int, total: int, status: str = "loading"):
        """Update loading progress information."""
        self.trading_state.loading_progress = {
            "status": status,
            "loaded": loaded,
            "total": total,
            "remaining": max(0, total - loaded),
            "progress": int((loaded / total) * 100) if total > 0 else 100
        }

    def add_symbols_to_trading(self, symbols: List[str]):
        """Add symbols to the current trading symbols list."""
        current_symbols = self.trading_state.symbols
        self.trading_state.symbols = list(set(current_symbols + symbols))

    def is_component_ready(self, component_name: str) -> bool:
        """Check if a specific component is ready/initialized."""
        component_map = {
            'websocket_manager': self.websocket_manager,
            'data_handler': self.data_handler,
            'simulated_trading_manager': self.simulated_trading_manager,
            'database_manager': self.database_manager,
            'websocket_client': self.websocket_client,
            'api_handlers': self.api_handlers,
            'dashboard_handlers': self.dashboard_handlers,
            'backtest_handlers': self.backtest_handlers,
            'trading_handlers': self.trading_handlers,
            'websocket_handlers': self.websocket_handlers,
            'data_handlers': self.data_handlers,
            'live_portfolio_handlers': self.live_portfolio_handlers,
            'vector_db_service': self.vector_db_service,
            'ml_optimizer': self.ml_optimizer
        }
        return component_map.get(component_name) is not None

    def get_all_components_status(self) -> Dict[str, bool]:
        """Get status of all components."""
        components = [
            'websocket_manager', 'data_handler', 'simulated_trading_manager',
            'database_manager', 'websocket_client', 'api_handlers',
            'dashboard_handlers', 'backtest_handlers', 'trading_handlers',
            'websocket_handlers', 'data_handlers', 'live_portfolio_handlers',
            'vector_db_service', 'ml_optimizer'
        ]
        return {comp: self.is_component_ready(comp) for comp in components}

    async def cleanup(self):
        """Clean up all resources and prepare for shutdown."""
        try:
            # Close simulated trading positions
            if self.simulated_trading_manager is not None:
                await self.simulated_trading_manager.force_close_all_positions("Application cleanup")
                # Deactivate session if exists
                if (self.database_manager is not None and
                    hasattr(self.simulated_trading_manager, 'session_id') and
                    self.simulated_trading_manager.session_id):
                    self.database_manager.deactivate_session(self.simulated_trading_manager.session_id)

            # Stop vector database services
            if self.vector_db_service:
                await self.vector_db_service.stop_services()

            # Clean up ML optimizer
            if self.ml_optimizer:
                # Any ML optimizer cleanup if needed
                self.ml_optimizer = None

            # Mark as shutdown
            self.set_shutdown(True)

        except Exception:
            # Re-raise to ensure proper error handling
            raise

    def __repr__(self) -> str:
        """String representation of application state."""
        components_status = self.get_all_components_status()
        ready_count = sum(components_status.values())
        total_count = len(components_status)
        return f"ApplicationState(initialized={self.initialized}, components_ready={ready_count}/{total_count})"
