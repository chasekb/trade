# Simulated Trading Tab Evidence

Date: 2026-06-21

## How the evidence was gathered
- Opened the trading dashboard at `http://localhost:3000`
- Switched to the Simulated Trading tab
- Forced the frontend start-trading call to fail fast in-browser so the client fell back to its local simulated-trading session path
- Let the tab run long enough to generate multiple trades and update the widgets
- Extracted the visible widget text and table rows from the live DOM

## Observed live session summary
At the time of capture, the simulated trading session showed:
- Total Net P&L: `-$2.07`
- Win Rate: `53.8%`
- Total Trades: `27`
- Cash Balance: `$9897.88`
- Total Value: `$9997.93`
- Positions Value: `$100.05`
- Active Positions: `1`
- Unrealized P&L: `$0.05`
- Realized P&L: `$0.04`
- Total Fees: `$2.16`
- Average Win: `$0.09`
- Average Loss: `$-0.09`
- Best Trade: `$0.14`
- Worst Trade: `$-0.15`
- Profit Factor: `1.08`
- Total Volume: `$2699.97`
- Avg Trade Size: `$100.00`
- Winning Trades: `7`
- Losing Trades: `6`

## Open positions widget evidence
Latest visible row:
- Symbol: `BTC-USD`
- Side: `BUY`
- Quantity: `0.0015`
- Entry: `$65101.9500`
- Current: `$65128.1100`
- Unrealized P&L: `$0.04`
- Opened: `6/21/2026, 9:01:41 PM`
- Action: `Close`

## Recent trades widget evidence
Latest visible rows:
- `6/21/2026, 9:01:41 PM | BTC-USD | SELL | 0.0015 | $65101.95 | $0.14`
- `6/21/2026, 9:01:41 PM | BTC-USD | BUY | 0.0015 | $65101.95 | $0.00`
- `6/21/2026, 9:01:32 PM | BTC-USD | BUY | 0.0015 | $65009.77 | $-0.15`
- `6/21/2026, 9:01:32 PM | BTC-USD | BUY | 0.0015 | $65009.77 | $0.00`
- `6/21/2026, 9:01:23 PM | BTC-USD | BUY | 0.0015 | $64915.21 | $-0.11`
- `6/21/2026, 9:01:23 PM | BTC-USD | SELL | 0.0015 | $64915.21 | $0.00`
- `6/21/2026, 9:01:14 PM | BTC-USD | SELL | 0.0015 | $64841.40 | $0.05`
- `6/21/2026, 9:01:14 PM | BTC-USD | SELL | 0.0015 | $64841.40 | $0.00`
- `6/21/2026, 9:01:05 PM | BTC-USD | SELL | 0.0015 | $64806.42 | $-0.02`
- `6/21/2026, 9:01:05 PM | BTC-USD | BUY | 0.0015 | $64806.42 | $0.00`

## Order book signals widget evidence
Latest visible row:
- Symbol: `BTC-USD`
- Price: `$65150.73`
- Signal: `BUY`
- Strength: `0.74`
- Spread: `0.0188%`
- Volume: `1490.00`
- Criteria: `✓ Squeeze ✓ Imbalance ○ Large Trade`
- ML analysis: `Win Probability: 0.6400%`, `Expected Return: 0.0294%`

## What this evidence supports
The live session demonstrated that the Simulated Trading tab is rendering and updating:
- Portfolio summary calculations
- Trade performance calculations
- Risk metrics
- Open positions table values
- Recent trades table values
- Order book signals table values

The backlog recommendations created from this evidence should each target one calculation or one widget at a time so the resulting test suite can prove each rendered value independently.
