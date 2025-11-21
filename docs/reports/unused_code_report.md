# Unused Code Report
Generated on 2025-11-20 12:30:46

## Summary
Total files with potential unused code: 71

## Detailed Findings

### `src/trade_bot/__init__.py`
- Line 4: **__getattr__** (unused function, 60% confidence)

### `src/trade_bot/backtest/backtest_components/backtest_result.py`
- Line 62: **get_summary** (unused method, 60% confidence)

### `src/trade_bot/backtest/backtest_components/data_processor.py`
- Line 15: **adjust_order_book_to_price** (unused method, 60% confidence)
- Line 62: **adjust_trades_to_price** (unused method, 60% confidence)
- Line 95: **process_trade_pairs** (unused method, 60% confidence)
- Line 139: **calculate_rolling_returns** (unused method, 60% confidence)
- Line 172: **calculate_volatility** (unused method, 60% confidence)
- Line 187: **calculate_correlation** (unused method, 60% confidence)
- Line 214: **detect_outliers** (unused method, 60% confidence)
- Line 243: **smooth_data** (unused method, 60% confidence)

### `src/trade_bot/backtest/backtest_components/equity_tracker.py`
- Line 22: **update_equity** (unused method, 60% confidence)
- Line 66: **get_equity_curve** (unused method, 60% confidence)
- Line 70: **get_equity_curve_df** (unused method, 60% confidence)
- Line 100: **get_equity_at_date** (unused method, 60% confidence)

### `src/trade_bot/backtest/backtest_components/metrics_calculator.py`
- Line 21: **calculate_metrics** (unused method, 60% confidence)
- Line 103: **calculate_advanced_metrics** (unused method, 60% confidence)
- Line 188: **calculate_rolling_metrics** (unused method, 60% confidence)

### `src/trade_bot/backtest/backtest_components/trade_executor.py`
- Line 33: **execute_trade** (unused method, 60% confidence)
- Line 125: **get_trades** (unused method, 60% confidence)

### `src/trade_bot/backtest/backtester.py`
- Line 504: **get_equity_curve_df** (unused method, 60% confidence)
- Line 514: **get_trades_df** (unused method, 60% confidence)

### `src/trade_bot/core/__init__.py`
- Line 4: **__getattr__** (unused function, 60% confidence)

### `src/trade_bot/core/config.py`
- Line 23: **websocket_url** (unused variable, 60% confidence)
- Line 37: **coinbase_max_concurrent_requests** (unused variable, 60% confidence)
- Line 38: **coinbase_min_request_interval** (unused variable, 60% confidence)
- Line 46: **enable_dca** (unused variable, 60% confidence)
- Line 53: **enable_buy_hold** (unused variable, 60% confidence)
- Line 59: **log_level** (unused variable, 60% confidence)

### `src/trade_bot/core/trading_bot.py`
- Line 165: **get_status** (unused method, 60% confidence)

### `src/trade_bot/core/universe_selector.py`
- Line 23: **symbol_rankings** (unused attribute, 60% confidence)
- Line 25: **select_symbols** (unused method, 60% confidence)
- Line 295: **get_universe_summary** (unused method, 60% confidence)

### `src/trade_bot/data/cached_data_provider.py`
- Line 137: **cleanup_expired_cache** (unused method, 60% confidence)
- Line 141: **clear_cache** (unused method, 60% confidence)
- Line 145: **reset_stats** (unused method, 60% confidence)

### `src/trade_bot/data/coinbase_portfolio_handler.py`
- Line 48: **portfolio_breakdown** (unused variable, 60% confidence)

### `src/trade_bot/data/data_components/api_client.py`
- Line 22: **public_base_url** (unused attribute, 60% confidence)
- Line 29: **uri** (unused variable, 100% confidence)
- Line 59: **_create_auth_headers** (unused method, 60% confidence)
- Line 122: **get_trades** (unused method, 60% confidence)
- Line 136: **get_product_info** (unused method, 60% confidence)

### `src/trade_bot/data/data_components/base_data_handler.py`
- Line 37: **clear_data** (unused method, 60% confidence)
- Line 42: **get_data_count** (unused method, 60% confidence)

### `src/trade_bot/data/data_handler.py`
- Line 28: **api_client** (unused attribute, 60% confidence)
- Line 123: **get_average_signal_price** (unused method, 60% confidence)
- Line 177: **save_ticker_data** (unused method, 60% confidence)
- Line 182: **save_trade_data** (unused method, 60% confidence)
- Line 187: **save_signal_data** (unused method, 60% confidence)
- Line 192: **save_level2_data** (unused method, 60% confidence)
- Line 197: **save_candles_data** (unused method, 60% confidence)
- Line 202: **save_matches_data** (unused method, 60% confidence)
- Line 207: **save_status_data** (unused method, 60% confidence)
- Line 212: **save_market_trades_data** (unused method, 60% confidence)

### `src/trade_bot/data/data_provider.py`
- Line 284: **get_historical_trades** (unused method, 60% confidence)
- Line 512: **get_product_stats** (unused method, 60% confidence)

### `src/trade_bot/data/http_session_manager.py`
- Line 102: **exc_tb** (unused variable, 100% confidence)
- Line 102: **exc_type** (unused variable, 100% confidence)
- Line 102: **exc_val** (unused variable, 100% confidence)
- Line 125: **close_http_session** (unused function, 60% confidence)

### `src/trade_bot/data/polars_optimizer.py`
- Line 29: **test_df** (unused variable, 60% confidence)
- Line 99: **analyze_order_book_polars** (unused method, 60% confidence)
- Line 158: **calculate_rolling_metrics_polars** (unused method, 60% confidence)
- Line 182: **batch_analyze_trades_polars** (unused method, 60% confidence)
- Line 200: **get_performance_stats** (unused method, 60% confidence)

### `src/trade_bot/data/websocket_client.py`
- Line 50: **authenticated_websocket_url** (unused attribute, 60% confidence)
- Line 59: **last_message_time** (unused attribute, 60% confidence)
- Line 65: **connection_attempts** (unused attribute, 60% confidence)
- Line 90: **last_message_time** (unused attribute, 60% confidence)
- Line 143: **connection_attempts** (unused attribute, 60% confidence)
- Line 149: **connection_attempts** (unused attribute, 60% confidence)
- Line 214: **authenticate** (unused method, 60% confidence)
- Line 325: **subscribe_to_matches** (unused method, 60% confidence)
- Line 329: **subscribe_to_status** (unused method, 60% confidence)
- Line 333: **subscribe_to_market_trades** (unused method, 60% confidence)
- Line 346: **get_subscription_info** (unused method, 60% confidence)

### `src/trade_bot/database/connection_pool.py`
- Line 14: **Empty** (unused import, 90% confidence)
- Line 14: **Queue** (unused import, 90% confidence)
- Line 109: **exc_tb** (unused variable, 100% confidence)
- Line 109: **exc_type** (unused variable, 100% confidence)
- Line 109: **exc_val** (unused variable, 100% confidence)
- Line 164: **close_all_pools** (unused function, 60% confidence)

### `src/trade_bot/database/database.py`
- Line 62: **save_backtest** (unused method, 60% confidence)
- Line 256: **clear_old_backtests** (unused method, 60% confidence)

### `src/trade_bot/ml/data_collector.py`
- Line 43: **prev_win_probability** (unused variable, 60% confidence)
- Line 44: **prev_expected_return** (unused variable, 60% confidence)
- Line 45: **prev_confidence** (unused variable, 60% confidence)
- Line 59: **duration_seconds** (unused variable, 60% confidence)
- Line 62: **entry_timestamp** (unused variable, 60% confidence)
- Line 63: **exit_timestamp** (unused variable, 60% confidence)
- Line 336: **row_factory** (unused attribute, 60% confidence)
- Line 366: **extract_order_book_snapshots** (unused method, 60% confidence)
- Line 419: **symbol_trades** (unused variable, 60% confidence)
- Line 424: **df_idx** (unused variable, 60% confidence)

### `src/trade_bot/ml/feature_engineer.py`
- Line 17: **ProcessedFeatures** (unused class, 60% confidence)
- Line 202: **impute_features** (unused method, 60% confidence)

### `src/trade_bot/ml/main.py`
- Line 49: **health** (unused function, 60% confidence)

### `src/trade_bot/ml/ml_optimizer.py`
- Line 10: **glob** (unused import, 90% confidence)
- Line 349: **y_new** (unused variable, 60% confidence)

### `src/trade_bot/ml/model_manager.py`
- Line 294: **evaluate_model_performance** (unused method, 60% confidence)
- Line 410: **cleanup_old_versions** (unused method, 60% confidence)

### `src/trade_bot/ml/model_trainer.py`
- Line 16: **Pipeline** (unused import, 90% confidence)
- Line 436: **load_model** (unused method, 60% confidence)
- Line 458: **cross_validate** (unused method, 60% confidence)

### `src/trade_bot/ml/server.py`
- Line 57: **vector_db_stats** (unused variable, 60% confidence)
- Line 112: **startup_event** (unused function, 60% confidence)
- Line 210: **get_model_status** (unused function, 60% confidence)
- Line 313: **update_model** (unused function, 60% confidence)

### `src/trade_bot/ml/training_manager.py`
- Line 88: **get_training_status** (unused method, 60% confidence)

### `src/trade_bot/ml/vector_database_service.py`
- Line 426: **get_service_urls** (unused method, 60% confidence)
- Line 458: **managed_services** (unused method, 60% confidence)
- Line 482: **start_vector_db_services** (unused function, 60% confidence)
- Line 488: **stop_vector_db_services** (unused function, 60% confidence)
- Line 494: **get_vector_db_status** (unused function, 60% confidence)

### `src/trade_bot/ml/vector_db_client.py`
- Line 124: **search_similar_vectors** (unused method, 60% confidence)
- Line 154: **get_vector_by_id** (unused method, 60% confidence)
- Line 171: **delete_vector** (unused method, 60% confidence)
- Line 209: **get_collection_stats** (unused method, 60% confidence)
- Line 229: **batch_search** (unused method, 60% confidence)
- Line 302: **store_feature_vector** (unused method, 60% confidence)
- Line 367: **cleanup_old_vectors** (unused method, 60% confidence)

### `src/trade_bot/trading/live_components/trade_executor.py`
- Line 23: **execute_trade** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/performance_tracker.py`
- Line 22: **update_equity** (unused method, 60% confidence)
- Line 81: **get_equity_curve** (unused method, 60% confidence)
- Line 207: **get_performance_summary** (unused method, 60% confidence)
- Line 223: **reset** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/portfolio.py`
- Line 100: **get_positions_by_symbol** (unused method, 60% confidence)
- Line 141: **get_summary** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/position.py`
- Line 97: **is_long** (unused method, 60% confidence)
- Line 101: **is_short** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/position_manager.py`
- Line 98: **update_position_price** (unused method, 60% confidence)
- Line 137: **get_positions_by_symbol** (unused method, 60% confidence)
- Line 157: **get_positions_summary** (unused method, 60% confidence)
- Line 174: **remove_closed_positions** (unused method, 60% confidence)
- Line 191: **clear_all_positions** (unused method, 60% confidence)
- Line 196: **get_symbols_with_positions** (unused method, 60% confidence)
- Line 200: **has_position** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/trade.py`
- Line 41: **is_sell** (unused method, 60% confidence)
- Line 53: **get_value** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_components/trade_executor.py`
- Line 56: **execute_buy** (unused method, 60% confidence)
- Line 112: **execute_sell** (unused method, 60% confidence)
- Line 171: **get_trades** (unused method, 60% confidence)
- Line 258: **clear_trades** (unused method, 60% confidence)

### `src/trade_bot/trading/simulated_trading_manager.py`
- Line 78: **position_count** (unused variable, 60% confidence)

### `src/trade_bot/trading/strategies/atr.py`
- Line 54: **add_ohlc** (unused method, 60% confidence)
- Line 171: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/base.py`
- Line 45: **get_strategy_name** (unused method, 60% confidence)
- Line 72: **reset_position** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/bollinger_bands.py`
- Line 239: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/buy_and_hold.py`
- Line 27: **buy_timestamp** (unused attribute, 60% confidence)
- Line 64: **buy_timestamp** (unused attribute, 60% confidence)
- Line 107: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/dca.py`
- Line 114: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/ema.py`
- Line 267: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/fibonacci.py`
- Line 29: **swing_high_time** (unused attribute, 60% confidence)
- Line 30: **swing_low_time** (unused attribute, 60% confidence)
- Line 64: **swing_high_idx** (unused variable, 60% confidence)
- Line 68: **swing_low_idx** (unused variable, 60% confidence)
- Line 179: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/macd.py`
- Line 144: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/ml_enhanced_orderbook.py`
- Line 53: **last_order_book_time** (unused attribute, 60% confidence)
- Line 89: **last_order_book_time** (unused attribute, 60% confidence)
- Line 288: **get_strategy_name** (unused method, 60% confidence)
- Line 324: **update_ml_accuracy** (unused method, 60% confidence)
- Line 324: **actual_outcome** (unused variable, 100% confidence)
- Line 324: **predicted_action** (unused variable, 100% confidence)

### `src/trade_bot/trading/strategies/ml_signal.py`
- Line 29: **prediction_timestamp** (unused variable, 60% confidence)
- Line 44: **lookback_periods** (unused attribute, 60% confidence)
- Line 45: **volume_percentiles** (unused attribute, 60% confidence)

### `src/trade_bot/trading/strategies/ml_strategy.py`
- Line 19: **MLStrategy** (unused class, 60% confidence)
- Line 34: **max_risk_per_trade** (unused attribute, 60% confidence)
- Line 48: **get_strategy_name** (unused method, 60% confidence)
- Line 201: **train_ml_model** (unused method, 60% confidence)
- Line 214: **update_prediction_accuracy** (unused method, 60% confidence)
- Line 221: **recent_prediction** (unused variable, 60% confidence)
- Line 259: **get_detailed_signal_analysis** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/orderbook.py`
- Line 43: **last_order_book_time** (unused attribute, 60% confidence)
- Line 74: **last_order_book_time** (unused attribute, 60% confidence)
- Line 224: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/rsi.py`
- Line 263: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/sma.py`
- Line 256: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/trading/strategies/stochastic.py`
- Line 146: **get_strategy_name** (unused method, 60% confidence)

### `src/trade_bot/web/models.py`
- Line 35: **created_at** (unused variable, 60% confidence)
- Line 38: **BacktestHistoryResponse** (unused class, 60% confidence)
- Line 46: **BacktestStatsResponse** (unused class, 60% confidence)
- Line 49: **successful_backtests** (unused variable, 60% confidence)
- Line 50: **average_return** (unused variable, 60% confidence)
- Line 51: **best_strategy** (unused variable, 60% confidence)
- Line 54: **TradingStartRequest** (unused class, 60% confidence)
- Line 58: **mode** (unused variable, 60% confidence)
- Line 62: **PositionCloseRequest** (unused class, 60% confidence)
- Line 64: **position_id** (unused variable, 60% confidence)
- Line 68: **SessionSaveRequest** (unused class, 60% confidence)
- Line 75: **DashboardStateRequest** (unused class, 60% confidence)

### `src/trade_bot/web/web_components/application_state.py`
- Line 78: **shutdown** (unused property, 60% confidence)
- Line 91: **reset_trading_state** (unused method, 60% confidence)

### `src/trade_bot/web/web_components/ml_dashboard.py`
- Line 14: **MLDashboardIntegration** (unused class, 60% confidence)
- Line 29: **set_ml_optimizer** (unused method, 60% confidence)
- Line 90: **trigger_model_training** (unused method, 60% confidence)
- Line 118: **trigger_model_update** (unused method, 60% confidence)
- Line 174: **get_pnl_tracking_data** (unused method, 60% confidence)
- Line 241: **get_ml_dashboard_data** (unused method, 60% confidence)

### `src/trade_bot/web/web_components/rate_limiter.py`
- Line 22: **is_allowed** (unused method, 60% confidence)
- Line 43: **get_remaining_requests** (unused method, 60% confidence)
- Line 54: **get_reset_time** (unused method, 60% confidence)

### `src/trade_bot/web/web_components/websocket_manager.py`
- Line 86: **send_personal_message** (unused method, 60% confidence)

### `src/trade_bot/web/web_handlers/backtest_handlers.py`
- Line 79: **backtester** (unused variable, 60% confidence)

### `src/trade_bot/web/web_handlers/data_handlers.py`
- Line 35: **_signal_cache** (unused attribute, 60% confidence)
- Line 50: **_signal_cache** (unused attribute, 60% confidence)
- Line 766: **volume_skew** (unused variable, 60% confidence)
- Line 797: **prediction_request** (unused variable, 60% confidence)
- Line 935: **_get_ml_server_status** (unused method, 60% confidence)
- Line 938: **cache_key** (unused variable, 60% confidence)
- Line 1031: **save_current_trading_state** (unused method, 60% confidence)

### `src/trade_bot/web/web_handlers/ml_handler.py`
- Line 76: **trigger_model_training** (unused function, 60% confidence)
- Line 82: **functools** (unused import, 90% confidence)
- Line 110: **get_training_status** (unused function, 60% confidence)
- Line 142: **get_ml_dashboard_data** (unused function, 60% confidence)
- Line 162: **get_pnl_trades_data** (unused function, 60% confidence)
- Line 173: **get_available_models** (unused function, 60% confidence)
- Line 184: **get_ml_config** (unused function, 60% confidence)
- Line 196: **update_ml_config** (unused function, 60% confidence)

### `src/trade_bot/web/web_handlers/trading_handlers.py`
- Line 873: **_recover_signals_from_database** (unused method, 60% confidence)

### `src/trade_bot/web/web_routes/api_routes.py`
- Line 13: **rate_limiter** (unused variable, 60% confidence)
- Line 35: **get_modular_dashboard** (unused function, 60% confidence)
- Line 50: **get_modular_dashboard_alt** (unused function, 60% confidence)
- Line 55: **get_legacy_dashboard** (unused function, 60% confidence)
- Line 62: **favicon** (unused function, 60% confidence)
- Line 122: **get_subscriptions_alt** (unused function, 60% confidence)
- Line 129: **get_realtime_status_alt** (unused function, 60% confidence)
- Line 136: **get_data_summary_alt** (unused function, 60% confidence)
- Line 143: **log_message** (unused function, 60% confidence)

### `src/trade_bot/web/web_routes/backtest_routes.py`
- Line 26: **run_backtests_alias** (unused function, 60% confidence)

### `src/trade_bot/web/web_routes/data_routes.py`
- Line 44: **get_orderbook_live_signals** (unused function, 60% confidence)
- Line 130: **get_active_session** (unused function, 60% confidence)
- Line 137: **save_session** (unused function, 60% confidence)
- Line 144: **save_dashboard_session** (unused function, 60% confidence)
- Line 152: **get_candles** (unused function, 60% confidence)

### `src/trade_bot/web/web_routes/live_portfolio_routes.py`
- Line 26: **get_live_portfolio_summary** (unused function, 60% confidence)
- Line 36: **get_live_portfolio_accounts** (unused function, 60% confidence)

### `src/trade_bot/web/web_routes/ml_routes.py`
- Line 32: **get_ml_analytics** (unused function, 60% confidence)

### `src/trade_bot/web/web_routes/trading_routes.py`
- Line 82: **start_async_trading** (unused function, 60% confidence)
- Line 164: **get_async_trading_loading_status** (unused function, 60% confidence)
- Line 181: **load_universe_data** (unused function, 60% confidence)
- Line 195: **load_symbols_data** (unused function, 60% confidence)
- Line 229: **get_simulated_trading_status_alt** (unused function, 60% confidence)
- Line 281: **get_trades_stats** (unused function, 60% confidence)
- Line 291: **get_trades_paginated** (unused function, 60% confidence)
- Line 301: **get_session_trades** (unused function, 60% confidence)

### `src/trade_bot/web/web_server.py`
- Line 39: **rate_limiter** (unused variable, 60% confidence)
- Line 88: **startup_event** (unused function, 60% confidence)
- Line 215: **shutdown_event** (unused function, 60% confidence)

## Note on False Positives
Static analysis tools like `vulture` may flag code as unused if it is:
- Called dynamically (e.g., via `getattr`)
- A callback or event handler (e.g., `startup_event`, API routes)
- Part of a public API consumed by external clients
- Accessed only via tests

Please review each item before deletion.