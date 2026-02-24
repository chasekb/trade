"""Tests for configuration management."""

import pytest
import os
from unittest.mock import patch
from datetime import datetime

from src.trade_bot.config import TradingConfig


class TestTradingConfig:
    """Test cases for TradingConfig."""
    
    def test_config_creation(self):
        """Test basic config creation."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase"
        )
        
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.passphrase == "test_passphrase"
        assert config.product_id == "BTC-USD"
        assert config.max_position_size == 1000.0
    
    def test_config_from_env(self):
        """Test config creation from environment variables."""
        env_vars = {
            "COINBASE_API_KEY": "env_key",
            "COINBASE_API_SECRET": "env_secret",
            "COINBASE_PASSPHRASE": "env_passphrase",
            "TRADING_PRODUCT_ID": "ETH-USD",
            "MAX_POSITION_SIZE": "2000.0",
            "STOP_LOSS_PERCENTAGE": "0.03",
            "TAKE_PROFIT_PERCENTAGE": "0.06"
        }
        
        with patch.dict(os.environ, env_vars):
            config = TradingConfig.from_env()
            
            assert config.api_key == "env_key"
            assert config.api_secret == "env_secret"
            assert config.passphrase == "env_passphrase"
            assert config.product_id == "ETH-USD"
            assert config.max_position_size == 2000.0
            assert config.stop_loss_percentage == 0.03
            assert config.take_profit_percentage == 0.06
    
    def test_config_validation_success(self):
        """Test successful config validation."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            max_position_size=1000.0,
            stop_loss_percentage=0.02,
            take_profit_percentage=0.04
        )
        
        # Should not raise any exception
        config.validate()
    
    def test_config_validation_missing_api_key(self):
        """Test config validation with missing API key."""
        config = TradingConfig(
            api_key="",
            api_secret="test_secret",
            passphrase="test_passphrase"
        )
        
        with pytest.raises(ValueError, match="COINBASE_API_KEY is required"):
            config.validate()
    
    def test_config_validation_missing_api_secret(self):
        """Test config validation with missing API secret."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="",
            passphrase="test_passphrase"
        )
        
        with pytest.raises(ValueError, match="COINBASE_API_SECRET is required"):
            config.validate()
    
    def test_config_validation_missing_passphrase(self):
        """Test config validation with missing passphrase."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase=""
        )
        
        with pytest.raises(ValueError, match="COINBASE_PASSPHRASE is required"):
            config.validate()
    
    def test_config_validation_invalid_position_size(self):
        """Test config validation with invalid position size."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            max_position_size=0.0
        )
        
        with pytest.raises(ValueError, match="MAX_POSITION_SIZE must be positive"):
            config.validate()
    
    def test_config_validation_invalid_stop_loss(self):
        """Test config validation with invalid stop loss percentage."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            stop_loss_percentage=1.5
        )
        
        with pytest.raises(ValueError, match="STOP_LOSS_PERCENTAGE must be between 0 and 1"):
            config.validate()
    
    def test_config_validation_invalid_take_profit(self):
        """Test config validation with invalid take profit percentage."""
        config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            take_profit_percentage=-0.1
        )
        
        with pytest.raises(ValueError, match="TAKE_PROFIT_PERCENTAGE must be between 0 and 1"):
            config.validate()
