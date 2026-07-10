# Plan: Robinhood Automated Options Trading Bot

**Date:** 2026-07-10
**Status:** active

## Goal

Build an automated trading bot that trades **options on US equities** through
Robinhood (via an MCP server the user will provide/connect later), aiming to
maximize risk-adjusted profit while enforcing a strict, hard-coded safety
margin. The strategy must be validated by backtesting (and later by a live
paper-trading trial) before any real capital is put at risk.

Confirmed scope (from planning discussion):
- **Asset class:** Options on equities.
- **Risk profile:** Moderate — target defined-risk structures (credit
  spreads, iron condors, covered calls, cash-secured puts), not naked/undefined
  risk positions.
- **Rollout path:** Backtest → shadow/paper trading → real money, in that
  order, with explicit go/no-go gates between stages.
- **Execution model:** Standalone Python service (not Claude-orchestrated).
  Claude Code is used to build/maintain it, not to run it live.
- **Broker connection:** No Robinhood MCP is attached to this dev session
  yet. The user has or will provide one. The bot is built against a
  `BrokerClient` interface so the real MCP-backed adapter can be dropped in
  without touching strategy/risk/backtest code.
- **Data:** Free sources for backtesting (e.g. yfinance/Stooq for underlying
  price history). Free *historical options chain* data does not really
  exist, so historical option prices for backtesting are **simulated** from
  underlying price history via an options pricing model (Black-Scholes +
  realized-vol proxy for IV), not replayed from real historical quotes. This
  is flagged clearly in all backtest reports so results aren't mistaken for
  exact historical fills.

## Architecture

```
robinhood-options-bot/
  config/            # settings.yaml: risk limits, strategy params, universe, mode flags
  data/               # cached historical price data (gitignored)
  src/
    data/             # price history fetchers + local cache
    options_pricing/  # Black-Scholes/Greeks, IV-rank/percentile calc
    strategy/         # signal generation + strategy definitions (spreads, condors, CC, CSP)
    risk/             # position sizing, exposure limits, drawdown circuit breaker, kill switch
    backtest/         # event-driven backtest engine, walk-forward harness, performance metrics
    broker/           # BrokerClient interface; MCP adapter + shadow/paper adapter
    execution/         # order manager, scheduler, daily run loop
    ledger/            # append-only trade/signal/risk-check event log (SQLite/Postgres)
    monitoring/        # alerting (webhook/email), health checks, divergence tracking
  dashboard/            # Streamlit app: live positions, P&L, risk-limit utilization, equity curve
  tests/
  scripts/            # run_backtest.py, run_paper.py, run_live.py
  notebooks/          # exploratory research
```

## Hard-coded safety rules (non-negotiable defaults)

- Defined-risk structures only at launch — no naked short options.
- Max risk per trade: ~2-3% of account equity (moderate risk budget).
- Portfolio-level exposure caps: max concurrent positions, max capital
  deployed at once (keep a cash/margin buffer), max aggregate
  delta/theta/vega exposure.
- Daily loss limit halts new entries for the rest of the day.
- Drawdown circuit breaker (account-level, e.g. 10-15%) halts all new
  entries pending manual review; does not auto-liquidate existing positions
  except via an explicit kill switch.
- Real order submission requires an explicit `LIVE_TRADING_ENABLED` flag,
  separate from the paper/shadow mode used by default.
- Every order (paper or live) is logged before submission with the full
  rationale (signal, sizing, risk checks passed).

## Steps

### Phase 0 — Scaffolding
- [ ] Repo layout, dependency management (uv/poetry), config schema (pydantic),
      structured logging.

### Phase 1 — Data layer
- [ ] Historical underlying price fetch + local cache (yfinance/Stooq).
- [ ] Live options chain fetch adapter (stubbed until MCP is connected).

### Phase 2 — Options pricing & signal engine
- [x] Black-Scholes pricing + Greeks; realized-vol and IV-rank/percentile
      calculation.
- [x] Entry/exit signal generation (trend/momentum filters + IV-rank timing)
      for each target strategy (credit spreads, iron condors, covered calls,
      cash-secured puts).

### Phase 3 — Risk engine
- [ ] Position sizing, exposure caps, drawdown circuit breaker, kill switch.
- [ ] Unit tests proving every limit actually blocks the trade it should.

### Phase 4 — Observability layer (ledger, dashboard, alerting)
- [ ] **Execution ledger**: append-only, timestamped records for every
      signal generated, order placed/filled/rejected, and risk-check
      outcome (pass/fail + why). SQLite to start, Postgres if it outgrows
      that. This is the source of truth everything else reads from —
      build it before the backtest engine so backtests and live/paper runs
      write to the same schema and are directly comparable.
- [ ] **Live state dashboard** (Streamlit, reading from the ledger):
      open positions with live P&L (realized + unrealized), aggregate
      Greeks exposure vs. caps, % of daily-loss/drawdown budget used,
      system health (last heartbeat, last successful broker call, data
      freshness).
- [ ] **Historical performance analytics**: equity curve, drawdown chart,
      win rate, profit factor, trade log — plus a **live-vs-backtest
      divergence tracker** that flags when real (paper/live) results start
      departing from what the simulated-pricing backtest predicted.
- [ ] **Alerting**: push notifications (webhook to Slack/Discord/ntfy.sh,
      or SMTP email) on risk-limit breaches, kill-switch trips, execution
      failures, and stale/missing market data — alerts must reach the user
      without anyone having to go look at a log.

### Phase 5 — Backtest engine
- [ ] Event-driven backtester using simulated option pricing, writing every
      simulated trade to the same ledger schema as Phase 4.
- [ ] Walk-forward validation (not single in-sample fit) across multiple
      market regimes (bull/bear/chop).
- [ ] Sensitivity analysis: IV assumption error, commissions/slippage, fill
      assumptions.
- [ ] Standard metrics: CAGR, Sharpe/Sortino, max drawdown, win rate, profit
      factor — reported with the "simulated options pricing" caveat front and
      center, viewable in the dashboard.

### Phase 6 — Broker adapter
- [ ] `BrokerClient` interface (quotes, chains, positions, place/cancel order).
- [ ] Shadow/paper adapter: real quotes, simulated fills, zero real orders.
- [ ] MCP-backed adapter wired in once the user's Robinhood MCP is available.

### Phase 7 — Paper trading trial
- [ ] Run shadow mode against live market data for a defined trial period,
      dashboard and alerting live the whole time.
- [ ] Compare live paper results vs. backtest expectations within tolerance
      (via the divergence tracker) before considering real capital.

### Phase 8 — Go-live gate (explicit, manual)
- [ ] Written go/no-go review against backtest + paper-trading results.
- [ ] Start real capital small and capped even after go-live.

## Notes

- Robinhood has no official public trading API; any MCP integration sits on
  top of reverse-engineered endpoints, which carries both technical risk
  (breakage) and account risk (ToS). The safety rules above (kill switch,
  paper-first, capped live rollout) are designed with that in mind
  regardless of strategy edge.
- Options backtesting caveat (simulated pricing, not replayed historical
  quotes) must be repeated in every backtest report — it's the single
  biggest source of false confidence in a plan like this.
- Waiting on: user's Robinhood MCP server details before Phase 6 (broker
  adapter) can be completed end-to-end. Phases 0-5 can proceed independently.
- The ledger (Phase 4) is built early and shared by backtest, paper, and
  live modes on purpose — it's what makes "does live match backtest"
  answerable later instead of a guess.

## Progress log

- **2026-07-10:** Phase 0 (scaffolding), Phase 1 (price history + realized
  vol), and the `BrokerClient` interface from Phase 6 (base interface +
  `ShadowBrokerClient` + `RobinhoodMCPBrokerClient` placeholder) are built
  under `robinhood-options-bot/`. 6/6 unit tests pass. Config enforces the
  live-trading gate (`mode: live` requires `live_trading_enabled: true` and
  is refused outright on the `mcp_placeholder` broker adapter).
  **Environment constraint found:** this session's network policy blocks
  `fc.yahoo.com` (yfinance's backend), returning 403 at the proxy. The data
  layer code is otherwise verified (unit tests, cache logic), but live
  fetches need either a network policy change on this environment (see
  Claude Code on the web docs) or a different data source/vendor.
  Documented in detail in `robinhood-options-bot/README.md` under "Known
  issues", including the three ways forward (change env network policy,
  fetch/cache data elsewhere and commit it, or try a different vendor).
- **2026-07-10 (Phase 2):** Black-Scholes pricing + Greeks
  (`options_pricing/black_scholes.py`, validated against textbook reference
  values and put-call parity), IV rank/percentile over the realized-vol
  proxy (`options_pricing/iv_rank.py`), a synthetic option chain builder
  bridging price history -> `OptionContract` objects
  (`options_pricing/simulated_chain.py`), defined-risk strategy builders for
  bull put spread / bear call spread / iron condor / cash-secured put /
  covered call (`strategy/definitions.py`), and a trend + IV-rank signal
  engine that defaults to credit spreads over CSP/covered-call when a trade
  is signaled at all, since credit spreads cap max loss at (width - credit)
  regardless of stock price (`strategy/signals.py`). 30/30 tests passing,
  none requiring network access.
