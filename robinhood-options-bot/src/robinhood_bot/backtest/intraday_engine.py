"""Intraday backtest engine: same-day (0DTE) credit spreads entered at
multiple fixed checkpoints per trading day, closed by profit-target/
stop-loss during the day or intrinsic-value settlement at the close.

This is a deliberately distinct strategy from backtest/engine.py's daily
30-DTE version, not a parameter tweak: the edge is compressed from weeks
into hours, so the entry cadence and position lifecycle differ, and
overtrading is a new risk that didn't exist when the strategy traded
roughly once a day (see RiskSettings.max_trades_per_day).

The *regime filter* -- should we be selling premium at all today, and in
which direction -- reuses the exact same validated daily trend/IV-rank/
vol-spike signals from strategy/signals.py, computed once per day from
daily bars. Only the intraday entry timing, option pricing (using
intraday realized vol, not the coarse daily figure), and 0DTE lifecycle
are new. Settlement, slippage, and position-group bookkeeping are
imported directly from backtest/engine.py rather than duplicated, since
those are genuinely DTE-agnostic.
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from robinhood_bot.backtest.engine import (
    MIN_SETTLEMENT_PRICE,
    _apply_slippage,
    _close_position_group,
    _count_open_position_groups,
    _reserved_risk_capital,
    _settle_expired_positions,
    _STRATEGY_BUILDERS,
)
from robinhood_bot.broker.base import OptionRight, OrderLeg, OrderStatus
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import RiskSettings
from robinhood_bot.data.price_history import realized_volatility
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.logging_setup import get_logger
from robinhood_bot.options_pricing.black_scholes import price_and_greeks
from robinhood_bot.options_pricing.iv_rank import iv_rank_series
from robinhood_bot.options_pricing.simulated_chain import (
    MARKET_CLOSE_UTC,
    build_simulated_chain,
    generate_strike_grid,
)
from robinhood_bot.risk.engine import RiskEngine
from robinhood_bot.strategy.signals import StrategyTag, is_volatility_spiking, recommend_strategy, trend_signal

log = get_logger(__name__)

DAILY_TREND_FAST, DAILY_TREND_SLOW = 20, 50
DAILY_IV_RANK_WINDOW = 252
MIN_DAILY_HISTORY = max(DAILY_IV_RANK_WINDOW, DAILY_TREND_SLOW) + 1
INTRADAY_VOL_WINDOW = 26  # ~1 trading day's worth of 15Min bars


@dataclass
class IntradayBacktestConfig:
    ticker: str
    starting_cash: float = 100_000
    risk_free_rate: float = 0.05
    spread_width: float = 2.0          # tighter than the daily strategy's 5.0 -- 0DTE premium is much smaller
    # generate_strike_grid's default increment is $5 at SPY's price level,
    # tuned for the daily strategy's 30-DTE strikes. Real SPY 0DTE options
    # actually trade in $1 increments (high liquidity, daily expirations)
    # -- using the $5 default here would make spread_width=2.0
    # unbuildable (minimum realized width on a $5 grid is $5, which blows
    # through even a generous max_width_multiple tolerance every time).
    strike_increment: float = 1.0
    iv_rank_threshold: float = 50.0
    slippage_pct: float = 0.0
    commission_per_contract: float = 0.0
    profit_target_pct: float = 0.50
    stop_loss_multiple: float = 2.0
    checkpoints_per_day: int = 3       # >= 2: last checkpoint is always settlement-only, never a new entry
    # Annualization factor for the intraday realized-vol proxy -- depends
    # on the bar timeframe. 6552 = 26 bars/day (15Min bars over a 6.5h
    # session) * 252 trading days/year. Must be changed if a different
    # intraday timeframe is used.
    bars_per_year: float = 6552.0


@dataclass
class IntradayBacktestResult:
    run_id: str
    ticker: str
    final_equity: float
    equity_curve: list[dict]


def _intraday_realized_vol(closes: pd.Series, window: int, bars_per_year: float) -> pd.Series:
    log_returns = np.log(closes / closes.shift(1))
    return log_returns.rolling(window).std() * (bars_per_year ** 0.5)


def _select_checkpoints(day_bars: pd.DataFrame, n: int) -> list[pd.Timestamp]:
    """Evenly spaced bar timestamps within one trading day's bars, always
    including the first and last bar. The last one returned is always
    treated as the day's settlement point -- see run_intraday_backtest."""
    n = max(n, 2)
    if len(day_bars) <= n:
        return list(day_bars.index)
    positions = sorted({round(i) for i in np.linspace(0, len(day_bars) - 1, n)})
    return [day_bars.index[p] for p in positions]


def run_intraday_backtest(
    daily_df: pd.DataFrame,
    intraday_df: pd.DataFrame,
    config: IntradayBacktestConfig,
    risk_settings: RiskSettings,
    ledger: Ledger,
    run_id: str | None = None,
) -> IntradayBacktestResult:
    """`daily_df` drives the once-a-day regime filter (trend/IV-rank/vol-
    spike), exactly as in backtest/engine.py. `intraday_df` drives entry
    timing, 0DTE option pricing, and position management within each day
    that has intraday bars available. Days present in `daily_df` but
    missing from `intraday_df` (e.g. before intraday history begins) are
    skipped for trading but still counted for the daily indicators' warmup."""
    run_id = run_id or f"intraday_backtest_{config.ticker}_{uuid.uuid4().hex[:8]}"
    mode = "backtest"

    if len(daily_df) < MIN_DAILY_HISTORY:
        raise ValueError(
            f"Need at least {MIN_DAILY_HISTORY} days of daily price history for "
            f"trend/IV-rank warmup; got {len(daily_df)}."
        )

    daily_vol = realized_volatility(daily_df)
    daily_iv_rank = iv_rank_series(daily_vol, window=DAILY_IV_RANK_WINDOW)
    intraday_vol = _intraday_realized_vol(intraday_df["Close"], INTRADAY_VOL_WINDOW, config.bars_per_year)
    intraday_dates = set(intraday_df.index.date)

    broker = ShadowBrokerClient(starting_cash=config.starting_cash)
    risk_engine = RiskEngine(risk_settings)

    for day_idx in range(MIN_DAILY_HISTORY, len(daily_df)):
        trading_day = daily_df.index[day_idx].date()
        if trading_day not in intraday_dates:
            continue
        day_bars = intraday_df[intraday_df.index.date == trading_day]
        if day_bars.empty:
            continue

        trend = trend_signal(daily_df.iloc[: day_idx + 1], fast=DAILY_TREND_FAST, slow=DAILY_TREND_SLOW)
        current_daily_iv_rank = daily_iv_rank.iloc[day_idx]
        vol_spiking = is_volatility_spiking(daily_vol.iloc[: day_idx + 1])
        strategy_tag = recommend_strategy(
            trend, current_daily_iv_rank, config.iv_rank_threshold, vol_spiking=vol_spiking,
        )

        risk_engine.mark_new_trading_day(trading_day, broker.get_account().equity)
        checkpoints = _select_checkpoints(day_bars, config.checkpoints_per_day)
        trades_today = 0

        for idx, checkpoint_ts in enumerate(checkpoints):
            is_settlement = idx == len(checkpoints) - 1
            spot = float(day_bars.loc[checkpoint_ts, "Close"])
            as_of = checkpoint_ts.to_pydatetime()
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            vol_now = float(intraday_vol.loc[checkpoint_ts])

            if is_settlement:
                _settle_expired_positions(broker, ledger, run_id, mode, trading_day, config.ticker, spot)
                continue

            _mark_intraday_positions_to_market(broker, config, spot, vol_now, as_of, trading_day)
            _manage_intraday_early_exits(broker, ledger, run_id, mode, config, as_of)

            if strategy_tag is StrategyTag.NO_TRADE or not (vol_now > 0):
                continue

            ledger.record_signal(
                run_id, mode, config.ticker, trend.value,
                None if pd.isna(current_daily_iv_rank) else float(current_daily_iv_rank),
                strategy_tag.value,
            )
            opened = _consider_new_intraday_trade(
                broker, risk_engine, ledger, run_id, mode, config,
                strategy_tag, spot, vol_now, as_of, trading_day, idx, trades_today,
            )
            if opened:
                trades_today += 1

        account = broker.get_account()
        risk_engine.update_equity(account.equity)
        ledger.record_equity_snapshot(run_id, mode, account.equity, account.cash)

    final_account = broker.get_account()
    return IntradayBacktestResult(
        run_id=run_id, ticker=config.ticker, final_equity=final_account.equity,
        equity_curve=ledger.equity_curve(run_id=run_id),
    )


def _consider_new_intraday_trade(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    mode: str,
    config: IntradayBacktestConfig,
    strategy_tag: StrategyTag,
    spot: float,
    vol_now: float,
    as_of: datetime,
    trading_day: date,
    checkpoint_idx: int,
    trades_today: int,
) -> bool:
    strikes = generate_strike_grid(
        spot, num_strikes=81, pct_step=config.strike_increment / spot, increment=config.strike_increment,
    )
    chain = build_simulated_chain(
        underlying=config.ticker, spot=spot, as_of=as_of, iv=vol_now,
        expirations=[trading_day], strikes=strikes, risk_free_rate=config.risk_free_rate,
    )

    builder = _STRATEGY_BUILDERS[strategy_tag]
    try:
        legs = builder(chain, width=config.spread_width)
    except (ValueError, IndexError):
        log.warning("intraday_backtest.strategy_build_failed", strategy_tag=strategy_tag.value, as_of=str(as_of))
        return False

    account = broker.get_account()
    open_groups = _count_open_position_groups(account)
    reserved_capital = _reserved_risk_capital(account)

    decision = risk_engine.evaluate_new_trade(account, legs, open_groups, reserved_capital, trades_today)
    ledger.record_risk_decision(
        run_id, mode, strategy_tag.value, decision.approved, decision.reason,
        decision.suggested_quantity, decision.max_loss_per_unit,
    )
    if not decision.approved:
        return False

    # Distinguishes this checkpoint's position group from any other
    # same-day, same-strategy-type entry at a different checkpoint --
    # without this, two "iron_condor" entries opened hours apart on the
    # same expiration would collide into one group under the
    # (strategy_tag, expiration) key that _count_open_position_groups /
    # _manage_intraday_early_exits / _settle_expired_positions all use,
    # since the daily engine (one entry per day, max) never had to
    # distinguish same-tag/same-expiration entries from each other.
    order_tag = f"{strategy_tag.value}_cp{checkpoint_idx}"

    scaled_legs = [
        OrderLeg(
            _apply_slippage(leg.contract, leg.side, config.slippage_pct),
            leg.side,
            leg.quantity * decision.suggested_quantity,
        )
        for leg in legs
    ]
    result = broker.place_order(scaled_legs, order_tag)
    ledger.record_order(run_id, mode, result)

    if config.commission_per_contract > 0 and result.status is OrderStatus.FILLED:
        total_contracts = sum(leg.quantity for leg in scaled_legs)
        broker.apply_cash_adjustment(-total_contracts * config.commission_per_contract)

    return result.status is OrderStatus.FILLED


def _mark_intraday_positions_to_market(
    broker: ShadowBrokerClient,
    config: IntradayBacktestConfig,
    spot: float,
    vol: float,
    as_of: datetime,
    trading_day: date,
) -> None:
    """Same purpose as backtest/engine.py's _mark_open_positions_to_market,
    but for same-day-expiring positions: that function skips anything
    expiring today (right, for a 30-DTE strategy, since "today" never
    equals a position's expiration until settlement), which would mean a
    0DTE position is *never* marked intraday. Uses actual fractional hours
    remaining until close, matching build_simulated_chain's same-day
    handling, instead of the daily version's whole-day count."""
    if vol <= 0:
        return
    close_dt = datetime.combine(trading_day, MARKET_CLOSE_UTC, tzinfo=as_of.tzinfo)
    seconds_remaining = max((close_dt - as_of).total_seconds(), 60.0)
    time_to_expiry_years = seconds_remaining / (365 * 24 * 3600)

    account = broker.get_account()
    for p in account.positions:
        if p.contract.underlying != config.ticker or p.contract.expiration != trading_day:
            continue
        greeks = price_and_greeks(
            spot=spot, strike=p.contract.strike, time_to_expiry_years=time_to_expiry_years,
            risk_free_rate=config.risk_free_rate, sigma=vol,
            is_call=p.contract.right is OptionRight.CALL,
        )
        mid = max(greeks.price, MIN_SETTLEMENT_PRICE)
        half_spread = max(mid * 0.03 / 2, 0.01)
        updated_contract = dataclasses.replace(
            p.contract,
            bid=round(max(mid - half_spread, 0.0), 2),
            ask=round(mid + half_spread, 2),
            last=round(mid, 2),
            delta=greeks.delta, gamma=greeks.gamma, theta=greeks.theta, vega=greeks.vega,
            implied_volatility=vol, as_of=as_of,
        )
        broker.remark_position(p.contract.occ_symbol, updated_contract)


def _manage_intraday_early_exits(
    broker: ShadowBrokerClient,
    ledger: Ledger,
    run_id: str,
    mode: str,
    config: IntradayBacktestConfig,
    as_of: datetime,
) -> None:
    """Same profit-target/stop-loss logic as backtest/engine.py's
    _manage_early_exits, minus the "skip today's expirations" filter --
    every intraday position expires today by construction, so that filter
    would skip everything. Requires _mark_intraday_positions_to_market to
    have run first this checkpoint."""
    account = broker.get_account()
    groups: dict[tuple, list] = {}
    for p in account.positions:
        if p.contract.underlying != config.ticker:
            continue
        groups.setdefault((p.strategy_tag, p.contract.expiration), []).append(p)

    for (strategy_tag, _expiration), positions in groups.items():
        entry_credit = 0.0
        current_cost_to_close = 0.0
        for p in positions:
            mid = (p.contract.bid + p.contract.ask) / 2
            if p.quantity < 0:
                entry_credit += p.average_open_price * 100 * abs(p.quantity)
                current_cost_to_close += mid * 100 * abs(p.quantity)
            else:
                entry_credit -= p.average_open_price * 100 * p.quantity
                current_cost_to_close -= mid * 100 * p.quantity

        if entry_credit <= 0:
            continue

        unrealized_pnl = entry_credit - current_cost_to_close
        if unrealized_pnl >= entry_credit * config.profit_target_pct:
            reason = "profit_target"
        elif unrealized_pnl <= -entry_credit * config.stop_loss_multiple:
            reason = "stop_loss"
        else:
            continue

        closing_prices = {
            p.contract.occ_symbol: (p.contract.bid + p.contract.ask) / 2 for p in positions
        }
        _close_position_group(
            broker, ledger, run_id, mode, strategy_tag, positions, closing_prices, reason, as_of,
        )
