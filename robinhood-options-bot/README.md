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

## Known issues

**Live price data is blocked in this Claude Code remote environment.**
`data/price_history.py` uses `yfinance`, which calls `fc.yahoo.com`. This
environment's outbound network proxy returns a 403 on that host
specifically (`policy denial or upstream failure` per
`$HTTPS_PROXY/__agentproxy/status`) -- PyPI/npm package installs work
(they're allowlisted for `pip install`), but general internet access to
data vendors is not. The code itself is verified by unit tests
(cache logic, parsing, realized-vol math) and by the Black-Scholes /
simulated-chain tests, which don't need the network -- only the actual
`fetch_price_history()` call against live Yahoo Finance is unverified.

Ways to unblock Phase 5 (backtesting needs real historical prices):
1. Change this environment's network policy to allow outbound access to a
   market data vendor's domain (Yahoo Finance, or a paid vendor's API).
   See the Claude Code on the web docs for how environment network policy
   is configured.
2. Fetch/cache the historical data on a machine with normal internet access
   and commit or upload the resulting Parquet files under
   `data/historical/` (gitignored today -- would need to be un-ignored or
   provided as a separate artifact).
3. Point `fetch_price_history` at a different vendor whose API might be
   reachable from this environment (untested; the current allowlist looks
   narrow, so this isn't guaranteed to help).

## Safety

`config/settings.yaml` controls `mode` (`shadow`/`live`) and
`live_trading_enabled`. Both must be set explicitly and in agreement for
real orders to ever be possible (`src/robinhood_bot/config.py` enforces
this), and `mode: live` is refused outright while the broker adapter is
still `mcp_placeholder`.
