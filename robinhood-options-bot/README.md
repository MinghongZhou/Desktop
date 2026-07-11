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

## Backtesting

```bash
python scripts/run_backtest.py --ticker SPY                                   # single backtest
python scripts/run_backtest.py --ticker SPY --n-folds 3                       # walk-forward, 3 folds
python scripts/run_backtest.py --ticker SPY --iv-sensitivity --execution-sensitivity
```

The engine (`src/robinhood_bot/backtest/engine.py`) is event-driven: it
walks day by day through price history, runs the same signal generation and
`RiskEngine` gate that live/paper trading use, fills through
`ShadowBrokerClient`, and settles expired positions automatically (real
brokers do this for you; the shadow broker doesn't, so the backtest loop
has to). Every signal, risk decision, order, and equity snapshot lands in
the same ledger a paper/live run would use.

`--iv-sensitivity` reruns the backtest at 0.7x/1.0x/1.3x the realized-vol
proxy used for option pricing -- the single biggest source of false
confidence in this project's numbers, since it's a model input standing in
for real historical IV (see "Known issues" below). `--execution-sensitivity`
does the same for fill quality (perfect fills vs. moderate/high slippage +
commission), since `ShadowBrokerClient` otherwise assumes free, exact-mid
fills.

**This script needs real historical price data over the network** — see
"Known issues" below. The backtest engine itself is fully tested against
synthetic price series (`tests/test_backtest_engine.py` and friends) and
doesn't depend on the network at all; only `fetch_price_history()`
(called by this script) does.

## Dashboard

Every run (backtest, paper, or live) writes to the same SQLite ledger
(`config/settings.yaml` -> `ledger.db_path`, default `data/ledger.sqlite3`).
View it with:

```bash
streamlit run dashboard/app.py
```

Shows the equity curve, drawdown, CAGR/Sharpe, and recent
signals/risk-decisions/orders. Filter to one run via the `run_id` box in the
sidebar, or leave it blank to see everything across all runs and modes.

Alerting is off by default (`config/settings.yaml` -> `alerting.enabled`).
Set `alerting.webhook_url` to a Slack/Discord-compatible incoming webhook
and flip `enabled: true` to page on halt-worthy risk events (kill switch,
drawdown circuit breaker, daily loss limit) -- routine per-trade
rejections don't page, only conditions that stop trading entirely.

## Broker adapters

Three `BrokerClient` implementations exist (`config/settings.yaml` ->
`broker.adapter`): `shadow` (simulated, default), `mcp_placeholder`
(raises until Robinhood's MCP is connected), and `alpaca` -- a real,
connectable adapter (`broker/alpaca.py`) added while Robinhood's MCP
connection is unavailable. Swapping between any of them is a one-line
config change; nothing in strategy/risk/backtest/execution code depends on
which one is active.

**The Alpaca adapter is unverified against a live call.** This
environment's network policy blocks Alpaca's API domains the same way it
blocks Yahoo Finance's (see "Known issues" below), so none of its HTTP
mappings have been exercised against a real response. Account/quote
endpoints (`/v2/account`, `/v2/stocks/.../quotes/latest`) are long-stable
Alpaca v2 APIs and lower risk; the options chain and multi-leg
(`order_class: "mleg"`) order endpoints are newer additions to Alpaca's API
and higher risk to have a subtly wrong field name or shape. Set
`ALPACA_API_KEY` / `ALPACA_API_SECRET` env vars (never in
`config/settings.yaml`) and run against a live paper account before
trusting this with real trades -- `tests/test_broker_alpaca.py` only
proves the adapter's own mapping logic is internally consistent against
fabricated example payloads, not that those payloads match Alpaca's actual
API.

## Known issues

**Live price data and broker APIs are blocked in this Claude Code remote
environment.** `data/price_history.py` uses `yfinance`, which calls
`fc.yahoo.com`; the Alpaca adapter calls `paper-api.alpaca.markets` and
`data.alpaca.markets`. This environment's outbound network proxy returns a
403 on all of these specifically (`policy denial or upstream failure` per
`$HTTPS_PROXY/__agentproxy/status`) -- PyPI/npm package installs work
(they're allowlisted for `pip install`), but general internet access to
financial data/broker vendors is not, and this doesn't appear to be
specific to any one vendor. The code itself is verified by unit tests
(cache logic, parsing, realized-vol math, Alpaca's own mapping logic,
Black-Scholes/simulated-chain tests), which don't need the network -- only
the actual live HTTP calls are unverified.

Ways to unblock real (non-simulated) data and broker access:
1. Change this environment's network policy to allow outbound access to
   the relevant vendor domain(s). See the Claude Code on the web docs for
   how environment network policy is configured. Since the block doesn't
   appear vendor-specific, this is the fix most likely to actually work,
   regardless of which data/broker vendor ends up in use.
2. Fetch/cache historical price data on a machine with normal internet
   access and commit or upload the resulting Parquet files under
   `data/historical/` (gitignored today -- would need to be un-ignored or
   provided as a separate artifact). Doesn't help with live broker access.
3. Run the paper/live trading loop itself from a machine/environment with
   normal internet access, using this repo -- the code doesn't require
   Claude Code's remote environment specifically, only this session's
   development work does.

## Safety

`config/settings.yaml` controls `mode` (`shadow`/`live`) and
`live_trading_enabled`. Both must be set explicitly and in agreement for
real orders to ever be possible (`src/robinhood_bot/config.py` enforces
this), and `mode: live` is refused outright while the broker adapter is
still `mcp_placeholder`.
