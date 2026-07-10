# Robinhood Options Trading Bot

Automated options trading bot targeting defined-risk strategies (credit
spreads, iron condors, covered calls, cash-secured puts) with hard-coded
risk limits, a full backtest before any live use, and an observability
layer (ledger + dashboard + alerting) shared across backtest, paper, and
live modes.

See `../plans/active/2026-07-10-robinhood-options-trading-bot.md` for the
full project plan and phase breakdown.

## Status

Phase 0 (scaffolding), Phase 1 (price history data layer), and the
`BrokerClient` interface (Phase 6) are in place. The Robinhood MCP adapter
(`src/robinhood_bot/broker/mcp_placeholder.py`) is a placeholder that
raises `NotImplementedError` until the real MCP connection is wired in --
everything else is built against the `BrokerClient` interface so that's a
drop-in swap when it's ready.

## Setup

```bash
cd robinhood-options-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Safety

`config/settings.yaml` controls `mode` (`shadow`/`live`) and
`live_trading_enabled`. Both must be set explicitly and in agreement for
real orders to ever be possible (`src/robinhood_bot/config.py` enforces
this), and `mode: live` is refused outright while the broker adapter is
still `mcp_placeholder`.
