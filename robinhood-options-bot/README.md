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

## Paper trading (Phase 7)

```bash
python scripts/run_paper.py --ticker SPY
```

A long-running daemon: shadow mode (simulated Black-Scholes option
pricing, same as backtesting) against a live-refreshing underlying price
feed, one trading day per cycle, running indefinitely. This is deliberately
**not** real-broker execution -- it uses the exact same per-day logic the
backtest engine uses (`backtest.engine.run_live_trading_day`, which calls
the identical `_run_trading_day` helper `run_backtest` uses internally),
so comparing a paper run's results against backtest expectations is
comparing the same code path on different data, not two different
implementations that happen to look similar.

Runs as a long-lived process, not a cron job re-invoked fresh each day --
broker and risk-engine state (positions, cash, peak equity, daily-loss
baseline) live in memory for the life of the process. Nothing persists to
disk between restarts yet; killing the process loses that in-memory state
and a restart starts a fresh paper account. State persistence across
restarts is a reasonable future addition but isn't needed for a
process that's meant to just stay running.

Wiring this to place *real* orders against a real broker (Alpaca or
Robinhood MCP) using real option chains is deliberately a separate,
not-yet-built code path -- swapping `ShadowBrokerClient` for a real
adapter here would place real orders priced off simulated Black-Scholes
chains instead of the broker's actual market, which is wrong. That's
Phase 8 territory and needs its own dedicated signal-to-real-chain
pathway, not just a broker swap.

**This script needs real historical price data over the network**, same
as backtesting -- see "Known issues" below.

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

**Verification status (updated 2026-07-11, after this environment's
network policy was widened):** `get_account()`, `get_quote()`, and
`get_option_chain()` have all been exercised against a real Alpaca paper
account. `get_option_chain()` was wrong on the first live call and is now
fixed: the underlying symbol belongs in the URL path
(`/v1beta1/options/snapshots/{underlying}`), not as a query param on a
path-less endpoint, and results are paginated (`next_page_token`), which
the original version silently didn't follow (truncated to page one). Both
are fixed and covered by tests now.

`place_order()` / `cancel_order()` remain **unverified** -- deliberately
not exercised against the live account, since doing so places a real
(paper-money, but real) order rather than just reading data. Multi-leg
(`order_class: "mleg"`) option orders are the highest-risk remaining
unverified surface in `broker/alpaca.py`. Set `ALPACA_API_KEY` /
`ALPACA_API_SECRET` env vars (never in `config/settings.yaml`) and test an
actual order against a paper account -- deliberately, not as a side effect
of something else -- before trusting this with real trades.
`tests/test_broker_alpaca.py` proves the adapter's mapping logic is
internally consistent against fabricated example payloads; for the
verified methods above, a live call also confirmed those payload shapes
match Alpaca's actual API.

## Known issues

**RESOLVED (2026-07-11): this environment's network policy was widened**
and now reaches Alpaca's API domains (`paper-api.alpaca.markets`,
`data.alpaca.markets`) -- confirmed via real calls, see "Broker adapters"
above. The `mcp_placeholder`/network-block section below is left for
historical context and because one piece of it is still relevant.

**`yfinance` (Yahoo Finance) still doesn't work, but for a different
reason now.** `data/price_history.py` calls `fc.yahoo.com` /
`query1.finance.yahoo.com`. With the network policy fixed, a plain `curl`
to Yahoo's chart endpoint gets a clean `HTTP 429` (rate-limited) rather
than a proxy block -- but `yfinance`'s own HTTP client (which impersonates
a browser's TLS fingerprint) gets a connection reset, consistently, across
retries. This looks like Yahoo Finance itself fingerprinting and blocking
`yfinance`'s traffic specifically -- a widely-reported, worsening problem
with that library from cloud/datacenter IPs, independent of this
environment. **Recommendation: don't chase this further** -- switch the
price-history data source to Alpaca's historical bars endpoint instead
(not yet wired up; `AlpacaBrokerClient` currently only covers the
`BrokerClient` interface, which doesn't include historical OHLCV bars).
Alpaca is already verified reachable and authenticated in this
environment, so this is a more reliable path than continuing to debug
`yfinance`/Yahoo.

Original (now resolved) network-block details, kept for context: PyPI/npm
package installs were always allowlisted for `pip install`, but general
internet access to financial data/broker vendors was blocked by default at
environment creation -- not specific to any one vendor. Fixed by widening
the environment's network policy (see the Claude Code on the web docs).

## Safety

`config/settings.yaml` controls `mode` (`shadow`/`live`) and
`live_trading_enabled`. Both must be set explicitly and in agreement for
real orders to ever be possible (`src/robinhood_bot/config.py` enforces
this), and `mode: live` is refused outright while the broker adapter is
still `mcp_placeholder`.
