"""Configuration management for the trading bot."""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class TradingConfig:
    """Configuration for the trading bot."""
    
    # Coinbase API credentials
    api_key: str
    api_secret: str
    passphrase: str
    
    # Trading parameters
    product_id: str = "BTC-USD"
    websocket_url: str = "wss://advanced-trade-ws.coinbase.com"
    
    # Risk management
    max_position_size: float = 1000.0
    stop_loss_percentage: float = 0.02  # 2%
    take_profit_percentage: float = 0.04  # 4%
    trading_fee_percentage: float = 0.001  # 0.1%
    
    # Dollar Cost Averaging (DCA) settings
    enable_dca: bool = False
    dca_amount: float = 100.0  # Fixed amount to invest per DCA period
    dca_frequency: int = 7  # Days between DCA investments
    dca_max_investments: int = 52  # Maximum number of DCA investments (1 year if weekly)
    dca_start_delay: int = 0  # Days to wait before starting DCA
    
    # Output settings
    output_dir: str = "outputs"
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Create configuration from environment variables."""
        return cls(
            api_key=os.getenv("COINBASE_API_KEY", ""),
            api_secret=os.getenv("COINBASE_API_SECRET", ""),
            passphrase=os.getenv("COINBASE_PASSPHRASE", ""),
            product_id=os.getenv("TRADING_PRODUCT_ID", "BTC-USD"),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "1000.0")),
            stop_loss_percentage=float(os.getenv("STOP_LOSS_PERCENTAGE", "0.02")),
            take_profit_percentage=float(os.getenv("TAKE_PROFIT_PERCENTAGE", "0.04")),
            trading_fee_percentage=float(os.getenv("TRADING_FEE_PERCENTAGE", "0.001")),
            enable_dca=os.getenv("ENABLE_DCA", "false").lower() == "true",
            dca_amount=float(os.getenv("DCA_AMOUNT", "100.0")),
            dca_frequency=int(os.getenv("DCA_FREQUENCY", "7")),
            dca_max_investments=int(os.getenv("DCA_MAX_INVESTMENTS", "52")),
            dca_start_delay=int(os.getenv("DCA_START_DELAY", "0")),
            output_dir=os.getenv("OUTPUT_DIR", "outputs"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.api_key:
            raise ValueError("COINBASE_API_KEY is required")
        if not self.api_secret:
            raise ValueError("COINBASE_API_SECRET is required")
        if not self.passphrase:
            raise ValueError("COINBASE_PASSPHRASE is required")
        if self.max_position_size <= 0:
            raise ValueError("MAX_POSITION_SIZE must be positive")
        if not 0 < self.stop_loss_percentage < 1:
            raise ValueError("STOP_LOSS_PERCENTAGE must be between 0 and 1")
        if not 0 < self.take_profit_percentage < 1:
            raise ValueError("TAKE_PROFIT_PERCENTAGE must be between 0 and 1")
        if self.dca_amount <= 0:
            raise ValueError("DCA_AMOUNT must be positive")
        if self.dca_frequency <= 0:
            raise ValueError("DCA_FREQUENCY must be positive")
        if self.dca_max_investments <= 0:
            raise ValueError("DCA_MAX_INVESTMENTS must be positive")
        if self.dca_start_delay < 0:
            raise ValueError("DCA_START_DELAY must be non-negative")
