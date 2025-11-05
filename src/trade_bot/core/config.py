"""Configuration management for the trading bot."""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


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
    
    # Symbol limits (configurable)
    max_symbols_per_request: int = 1000  # Maximum symbols per API request
    max_universe_size: int = 500  # Maximum universe size for trading
    max_positions_per_session: int = 100  # Maximum positions per trading session

    # API Rate limiting (configurable)
    coinbase_max_concurrent_requests: int = 5  # Maximum concurrent requests to Coinbase API
    coinbase_min_request_interval: float = 0.1  # Minimum seconds between requests (100ms)
    coinbase_rate_limit_enabled: bool = True  # Enable/disable rate limiting

    # ML server configuration
    ml_server_host: str = "ml-server"  # ML server host
    ml_server_port: int = 8002  # ML server port
    
    # Dollar Cost Averaging (DCA) settings
    enable_dca: bool = False
    dca_amount: float = 100.0  # Fixed amount to invest per DCA period
    dca_frequency: int = 7  # Days between DCA investments
    dca_max_investments: int = 52  # Maximum number of DCA investments (1 year if weekly)
    dca_start_delay: int = 0  # Days to wait before starting DCA
    
    # Buy and Hold settings
    enable_buy_hold: bool = False  # If True, hold positions indefinitely instead of using stop/loss
    buy_hold_exit_condition: str = "never"  # Options: "never", "end_of_period", "profit_target"
    buy_hold_profit_target: float = 0.0  # Profit target for buy and hold (0 = no target)
    
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
            max_symbols_per_request=int(os.getenv("MAX_SYMBOLS_PER_REQUEST", "1000")),
            max_universe_size=int(os.getenv("MAX_UNIVERSE_SIZE", "500")),
            max_positions_per_session=int(os.getenv("MAX_POSITIONS_PER_SESSION", "100")),
            coinbase_max_concurrent_requests=int(os.getenv("COINBASE_MAX_CONCURRENT_REQUESTS", "5")),
            coinbase_min_request_interval=float(os.getenv("COINBASE_MIN_REQUEST_INTERVAL", "0.1")),
            coinbase_rate_limit_enabled=os.getenv("COINBASE_RATE_LIMIT_ENABLED", "true").lower() == "true",
            ml_server_host=os.getenv("ML_SERVER_HOST", "ml-server"),
            ml_server_port=int(os.getenv("ML_SERVER_PORT", "8002")),
            enable_dca=os.getenv("ENABLE_DCA", "false").lower() == "true",
            dca_amount=float(os.getenv("DCA_AMOUNT", "100.0")),
            dca_frequency=int(os.getenv("DCA_FREQUENCY", "7")),
            dca_max_investments=int(os.getenv("DCA_MAX_INVESTMENTS", "52")),
            dca_start_delay=int(os.getenv("DCA_START_DELAY", "0")),
            enable_buy_hold=os.getenv("ENABLE_BUY_HOLD", "false").lower() == "true",
            buy_hold_exit_condition=os.getenv("BUY_HOLD_EXIT_CONDITION", "never"),
            buy_hold_profit_target=float(os.getenv("BUY_HOLD_PROFIT_TARGET", "0.0")),
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
        
        # Validate API key format (Coinbase API keys are typically 32 characters)
        if len(self.api_key) != 32:
            raise ValueError("COINBASE_API_KEY must be 32 characters long")
        if not self.api_key.isalnum():
            raise ValueError("COINBASE_API_KEY must contain only alphanumeric characters")
        
        # Validate API secret format (Coinbase API secrets are typically 88 characters base64)
        if len(self.api_secret) != 88:
            raise ValueError("COINBASE_API_SECRET must be 88 characters long")
        if not self.api_secret.replace('+', '').replace('/', '').replace('=', '').isalnum():
            raise ValueError("COINBASE_API_SECRET must be valid base64 format")
        
        # Validate passphrase (should not be empty and reasonable length)
        if len(self.passphrase) < 8:
            raise ValueError("COINBASE_PASSPHRASE must be at least 8 characters long")
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
        if self.buy_hold_exit_condition not in ["never", "end_of_period", "profit_target"]:
            raise ValueError("BUY_HOLD_EXIT_CONDITION must be 'never', 'end_of_period', or 'profit_target'")
        if self.buy_hold_profit_target < 0:
            raise ValueError("BUY_HOLD_PROFIT_TARGET must be non-negative")
