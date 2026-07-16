"""Event-driven backtest engine.

Walks day by day through historical underlying prices, generating signals
(trend + IV rank), sizing/gating trades through the same `RiskEngine` used
live, and filling them through `ShadowBrokerClient` -- the exact same
broker implementation paper trading uses. Every signal, risk decision,
order, and end-of-day equity snapshot is written to the same ledger schema
live/paper runs use, so Phase 7's live-vs-backtest comparison is a query
against this data, not a guess.

*** Option prices throughout are Black-Scholes simulations calibrated to
realized volatility, not replayed historical option quotes. See
data/price_history.py and options_pricing/simulated_chain.py for why. ***
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

import pandas as pd

from robinhood_bot.broker.base import (
    Account,
    OptionContract,
    OptionRight,
    OrderLeg,
    OrderSide,
    OrderStatus,
    Position,
)
from robinhood_bot.broker.shadow import ShadowBrokerClient
from robinhood_bot.config import RiskSettings
from robinhood_bot.data.price_history import realized_volatility
from robinhood_bot.ledger.store import Ledger
from robinhood_bot.logging_setup import get_logger
from robinhood_bot.options_pricing.black_scholes import price_and_greeks
from robinhood_bot.options_pricing.iv_rank import iv_rank_series
from robinhood_bot.options_pricing.simulated_chain import build_simulated_chain, generate_expirations
from robinhood_bot.risk.engine import RiskEngine
from robinhood_bot.risk.position_sizing import UndefinedRiskError, estimate_max_loss_per_unit
from robinhood_bot.strategy.definitions import bear_call_spread, bull_put_spread, iron_condor
from robinhood_bot.strategy.signals import (
    StrategyTag,
    is_volatility_spiking,
    recommend_strategy,
    trend_signal,
)

log = get_logger(__name__)

_STRATEGY_BUILDERS = {
    StrategyTag.BULL_PUT_SPREAD: bull_put_spread,
    StrategyTag.BEAR_CALL_SPREAD: bear_call_spread,
    StrategyTag.IRON_CONDOR: iron_condor,
}

IV_RANK_WINDOW = 252
TREND_FAST, TREND_SLOW = 20, 50
MIN_HISTORY_DAYS = max(IV_RANK_WINDOW, TREND_SLOW) + 1
MIN_SETTLEMENT_PRICE = 0.01  # see _settle_expired_positions for why this isn't 0.0


@dataclass
class BacktestConfig:
    ticker: str
    starting_cash: float = 100_000
    risk_free_rate: float = 0.05
    dte_target: int = 30
    spread_width: float = 5.0
    iv_rank_threshold: float = 50.0
    slippage_pct: float = 0.0          # fraction of mid, worse for the trader on each leg
    commission_per_contract: float = 0.0
    iv_multiplier: float = 1.0         # scales the realized-vol proxy fed into option pricing only
    enable_early_exit: bool = True
    profit_target_pct: float = 0.50    # close early once unrealized profit reaches this fraction of credit received
    stop_loss_multiple: float = 2.0    # close early once unrealized loss reaches this multiple of credit received
    # Off by default -- existing callers (including the live paper trial)
    # get identical behavior unless they explicitly opt in and pass a
    # sentiment_series into run_backtest/run_live_trading_day. See
    # sentiment/scorer.py for how that series is built.
    sentiment_filter_enabled: bool = False
    sentiment_block_threshold: float = 0.15  # block a directional trade if news sentiment contradicts it by more than this


@dataclass
class BacktestResult:
    run_id: str
    ticker: str
    final_equity: float
    equity_curve: list[dict]


def run_backtest(
    price_df: pd.DataFrame,
    config: BacktestConfig,
    risk_settings: RiskSettings,
    ledger: Ledger,
    run_id: str | None = None,
    sentiment_series: pd.Series | None = None,
) -> BacktestResult:
    """`sentiment_series`, if given, must be aligned to `price_df.index`
    (same length, same positional order -- see
    sentiment/scorer.py's daily_sentiment_series). Only consulted at all
    when `config.sentiment_filter_enabled` is True."""
    run_id = run_id or f"backtest_{config.ticker}_{uuid.uuid4().hex[:8]}"
    mode = "backtest"

    if len(price_df) < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Need at least {MIN_HISTORY_DAYS} days of price history for "
            f"IV-rank/trend warmup; got {len(price_df)}."
        )

    vol_series = realized_volatility(price_df)
    iv_rank = iv_rank_series(vol_series, window=IV_RANK_WINDOW)

    broker = ShadowBrokerClient(starting_cash=config.starting_cash)
    risk_engine = RiskEngine(risk_settings)

    for i in range(MIN_HISTORY_DAYS, len(price_df)):
        _run_trading_day(broker, risk_engine, ledger, run_id, mode, config, price_df, vol_series, iv_rank, i,
                          sentiment_series=sentiment_series)

    final_account = broker.get_account()
    return BacktestResult(
        run_id=run_id,
        ticker=config.ticker,
        final_equity=final_account.equity,
        equity_curve=ledger.equity_curve(run_id=run_id),
    )


def run_live_trading_day(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    config: BacktestConfig,
    price_df: pd.DataFrame,
    mode: str = "paper",
    sentiment_series: pd.Series | None = None,
) -> None:
    """Runs exactly one trading day -- the LAST row of `price_df` -- through
    the identical per-day logic `run_backtest` uses for every historical
    day. This is what makes comparing paper/live results against backtest
    expectations meaningful instead of apples-to-oranges: it's not
    "similar" logic, it's the same function.

    `price_df` must already include at least `MIN_HISTORY_DAYS` of history
    ending on the day to trade. Call this once per trading day with an
    updated `price_df`, reusing the same `broker`/`risk_engine`/`run_id`
    across calls so state (positions, cash, peak equity, daily-loss
    baseline) carries over -- see execution/paper_loop.py, which is what
    actually does that in a long-running process.

    Still simulates option pricing via Black-Scholes even though the
    underlying price feed can be live/real -- this is Phase 7's "shadow
    mode against live market data," not a real-broker execution path. A
    real adapter (Alpaca/Robinhood MCP) placing real orders off real
    option chains is a deliberately separate, not-yet-built code path;
    see the plan's Phase 7/8 notes for why that's not just a broker swap.
    """
    if len(price_df) < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Need at least {MIN_HISTORY_DAYS} days of price history for "
            f"IV-rank/trend warmup; got {len(price_df)}."
        )
    vol_series = realized_volatility(price_df)
    iv_rank = iv_rank_series(vol_series, window=IV_RANK_WINDOW)
    _run_trading_day(
        broker, risk_engine, ledger, run_id, mode, config,
        price_df, vol_series, iv_rank, len(price_df) - 1,
        sentiment_series=sentiment_series,
    )


def _run_trading_day(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    mode: str,
    config: BacktestConfig,
    price_df: pd.DataFrame,
    vol_series: pd.Series,
    iv_rank: pd.Series,
    i: int,
    sentiment_series: pd.Series | None = None,
) -> None:
    as_of = price_df.index[i].to_pydatetime().replace(tzinfo=timezone.utc)
    as_of_date = as_of.date()
    spot = float(price_df["Close"].iloc[i])
    current_vol = vol_series.iloc[i]

    risk_engine.mark_new_trading_day(as_of_date, broker.get_account().equity)
    _settle_expired_positions(broker, ledger, run_id, mode, as_of_date, config.ticker, spot)
    _mark_open_positions_to_market(broker, config, spot, current_vol, as_of, as_of_date)
    _manage_early_exits(broker, ledger, run_id, mode, config, as_of_date, as_of)

    history_slice = price_df.iloc[: i + 1]
    trend = trend_signal(history_slice, fast=TREND_FAST, slow=TREND_SLOW)
    current_iv_rank = iv_rank.iloc[i]
    vol_spiking = is_volatility_spiking(vol_series.iloc[: i + 1])

    strategy_tag = recommend_strategy(
        trend, current_iv_rank, config.iv_rank_threshold, vol_spiking=vol_spiking,
    )

    if config.sentiment_filter_enabled and sentiment_series is not None:
        sentiment_today = sentiment_series.iloc[i]
        if pd.notna(sentiment_today):
            # Iron condor (neutral) isn't blocked -- it has no directional
            # stance for news to contradict. A directional bet fighting
            # strongly-opposed news is the one case this filter exists for.
            if strategy_tag is StrategyTag.BULL_PUT_SPREAD and sentiment_today < -config.sentiment_block_threshold:
                strategy_tag = StrategyTag.NO_TRADE
            elif strategy_tag is StrategyTag.BEAR_CALL_SPREAD and sentiment_today > config.sentiment_block_threshold:
                strategy_tag = StrategyTag.NO_TRADE

    ledger.record_signal(
        run_id, mode, config.ticker, trend.value,
        None if pd.isna(current_iv_rank) else float(current_iv_rank),
        strategy_tag.value,
    )

    if strategy_tag is not StrategyTag.NO_TRADE and pd.notna(current_vol) and current_vol > 0:
        _consider_new_trade(
            broker, risk_engine, ledger, run_id, mode, config,
            strategy_tag, spot, float(current_vol), as_of, as_of_date,
        )

    account = broker.get_account()
    risk_engine.update_equity(account.equity)
    ledger.record_equity_snapshot(run_id, mode, account.equity, account.cash)


def _consider_new_trade(
    broker: ShadowBrokerClient,
    risk_engine: RiskEngine,
    ledger: Ledger,
    run_id: str,
    mode: str,
    config: BacktestConfig,
    strategy_tag: StrategyTag,
    spot: float,
    current_vol: float,
    as_of: datetime,
    as_of_date: date,
) -> None:
    chain = build_simulated_chain(
        underlying=config.ticker,
        spot=spot,
        as_of=as_of,
        # iv_multiplier only affects the price options are simulated at,
        # not the realized-vol-based IV-rank signal that decided to trade
        # (that's computed once up front in run_backtest, unscaled) --
        # this isolates sensitivity testing to "was the pricing model
        # right," not "would the strategy have even fired differently."
        iv=current_vol * config.iv_multiplier,
        expirations=generate_expirations(as_of_date, dte_targets=[config.dte_target]),
        risk_free_rate=config.risk_free_rate,
    )

    builder = _STRATEGY_BUILDERS[strategy_tag]
    try:
        legs = builder(chain, width=config.spread_width)
    except (ValueError, IndexError):
        log.warning("backtest.strategy_build_failed", strategy_tag=strategy_tag.value, as_of=str(as_of_date))
        return

    account = broker.get_account()
    open_groups = _count_open_position_groups(account)
    reserved_capital = _reserved_risk_capital(account)

    decision = risk_engine.evaluate_new_trade(account, legs, open_groups, reserved_capital)
    ledger.record_risk_decision(
        run_id, mode, strategy_tag.value, decision.approved, decision.reason,
        decision.suggested_quantity, decision.max_loss_per_unit,
    )
    if not decision.approved:
        return

    scaled_legs = [
        OrderLeg(
            _apply_slippage(leg.contract, leg.side, config.slippage_pct),
            leg.side,
            leg.quantity * decision.suggested_quantity,
        )
        for leg in legs
    ]
    result = broker.place_order(scaled_legs, strategy_tag.value)
    ledger.record_order(run_id, mode, result)

    if config.commission_per_contract > 0 and result.status is OrderStatus.FILLED:
        total_contracts = sum(leg.quantity for leg in scaled_legs)
        broker.apply_cash_adjustment(-total_contracts * config.commission_per_contract)


def _apply_slippage(contract: OptionContract, side: OrderSide, slippage_pct: float) -> OptionContract:
    """Shifts bid/ask so the fill (at their midpoint) is worse for the
    trader by `slippage_pct` of mid -- lower for a sell, higher for a buy."""
    if slippage_pct <= 0:
        return contract
    mid = (contract.bid + contract.ask) / 2
    is_buy = side in (OrderSide.BUY_TO_OPEN, OrderSide.BUY_TO_CLOSE)
    shift = mid * slippage_pct * (1 if is_buy else -1)
    return dataclasses.replace(
        contract,
        bid=max(contract.bid + shift, 0.0),
        ask=max(contract.ask + shift, 0.0),
    )


def _count_open_position_groups(account: Account) -> int:
    """Each opening order's legs share (strategy_tag, expiration) by
    construction (see strategy/definitions.py), so that pair is a reliable
    proxy for "one open strategy instance" without needing separate
    position-grouping bookkeeping."""
    return len({(p.strategy_tag, p.contract.expiration) for p in account.positions})


def _reserved_risk_capital(account: Account) -> float:
    groups: dict[tuple, list[Position]] = {}
    for p in account.positions:
        groups.setdefault((p.strategy_tag, p.contract.expiration), []).append(p)

    total = 0.0
    for positions in groups.values():
        quantity = abs(positions[0].quantity)
        legs = [
            OrderLeg(
                p.contract,
                OrderSide.SELL_TO_OPEN if p.quantity < 0 else OrderSide.BUY_TO_OPEN,
                1,
            )
            for p in positions
        ]
        try:
            total += estimate_max_loss_per_unit(legs) * quantity
        except UndefinedRiskError:
            continue
    return total


def _close_position_group(
    broker: ShadowBrokerClient,
    ledger: Ledger,
    run_id: str,
    mode: str,
    strategy_tag: str,
    positions: list[Position],
    closing_price_by_symbol: dict[str, float],
    reason_suffix: str,
    as_of: datetime,
) -> None:
    """Shared by expiration settlement and early-exit management: builds
    closing legs (BUY_TO_CLOSE for shorts, SELL_TO_CLOSE for longs) at the
    given per-symbol closing price and places the order. `reason_suffix`
    (e.g. "expiration_settlement", "profit_target", "stop_loss") is
    appended to the strategy_tag so the ledger records *why* a position
    closed, not just that it did."""
    legs = []
    for p in positions:
        price = closing_price_by_symbol[p.contract.occ_symbol]
        closing_contract = dataclasses.replace(
            p.contract, bid=price, ask=price, last=price, as_of=as_of,
        )
        side = OrderSide.BUY_TO_CLOSE if p.quantity < 0 else OrderSide.SELL_TO_CLOSE
        legs.append(OrderLeg(closing_contract, side, abs(p.quantity)))

    result = broker.place_order(legs, strategy_tag=f"{strategy_tag}_{reason_suffix}")
    ledger.record_order(run_id, mode, result)


def _settle_expired_positions(
    broker: ShadowBrokerClient,
    ledger: Ledger,
    run_id: str,
    mode: str,
    as_of_date: date,
    ticker: str,
    spot: float,
) -> None:
    """The real broker (and Robinhood itself) settles expired options
    automatically; ShadowBrokerClient doesn't, since nothing else in the
    system knows what "today" is except the backtest loop. Settlement
    prices are intrinsic value with a small floor (see
    MIN_SETTLEMENT_PRICE) rather than exactly 0.0, so a worthless
    expiration doesn't collide with place_order()'s "no market" rejection
    guard, which uses bid == ask == 0.0 to mean something different
    (a dead/illiquid contract, not a legitimate zero settlement)."""
    account = broker.get_account()
    expired = [
        p for p in account.positions
        if p.contract.underlying == ticker and p.contract.expiration <= as_of_date
    ]
    if not expired:
        return

    groups: dict[tuple, list[Position]] = {}
    for p in expired:
        groups.setdefault((p.strategy_tag, p.contract.expiration), []).append(p)

    settle_ts = datetime.combine(as_of_date, datetime.min.time(), tzinfo=timezone.utc)
    for (strategy_tag, _expiration), positions in groups.items():
        closing_prices = {}
        for p in positions:
            greeks = price_and_greeks(
                spot=spot, strike=p.contract.strike, time_to_expiry_years=0,
                risk_free_rate=0.0, sigma=1.0, is_call=p.contract.right is OptionRight.CALL,
            )
            closing_prices[p.contract.occ_symbol] = max(greeks.price, MIN_SETTLEMENT_PRICE)
        _close_position_group(
            broker, ledger, run_id, mode, strategy_tag, positions,
            closing_prices, "expiration_settlement", settle_ts,
        )


def _mark_open_positions_to_market(
    broker: ShadowBrokerClient,
    config: BacktestConfig,
    spot: float,
    vol: float,
    as_of: datetime,
    as_of_date: date,
) -> None:
    """Real brokers mark open positions to the live market automatically;
    the shadow broker doesn't (see ShadowBrokerClient.remark_position's
    docstring), so the backtest loop has to do it explicitly, every day,
    for every still-open position. Without this, `get_account().equity`
    silently uses each position's *fill-time* price forever, understating
    real day-to-day P&L swings until the position closes -- a real bug
    found and fixed while building the early-exit logic below, which
    can't work correctly without accurate current marks either. Skips
    positions expiring today; `_settle_expired_positions` handles those
    with proper intrinsic-value pricing instead."""
    if pd.isna(vol) or vol <= 0:
        return  # no valid vol estimate yet (early warmup); leave marks as-is for this one day
    account = broker.get_account()
    for p in account.positions:
        if p.contract.underlying != config.ticker or p.contract.expiration <= as_of_date:
            continue
        time_to_expiry_years = (p.contract.expiration - as_of_date).days / 365
        greeks = price_and_greeks(
            spot=spot, strike=p.contract.strike, time_to_expiry_years=time_to_expiry_years,
            risk_free_rate=config.risk_free_rate, sigma=vol * config.iv_multiplier,
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


def _manage_early_exits(
    broker: ShadowBrokerClient,
    ledger: Ledger,
    run_id: str,
    mode: str,
    config: BacktestConfig,
    as_of_date: date,
    as_of: datetime,
) -> None:
    """Closes a position early if it's captured most of its max profit
    (locking in gains before gamma risk increases near expiration -- a
    standard practice among systematic premium sellers) or if unrealized
    loss has grown too large relative to the credit collected (a
    stop-loss, capping downside before expiration forces the full max
    loss). Without this, a position opened weeks before a volatility
    spike stays fully exposed for its entire remaining life regardless of
    what happens in between -- see is_volatility_spiking's docstring in
    strategy/signals.py for the walk-forward finding that motivated this:
    that guard only blocks *new* entries during a spike, and does nothing
    for positions already open when one hits.

    Requires `_mark_open_positions_to_market` to have run first for
    today's prices to be current; relies on each position's
    `average_open_price` (preserved by both remark_position and normal
    fills) to reconstruct the original entry credit."""
    if not config.enable_early_exit:
        return

    account = broker.get_account()
    groups: dict[tuple, list[Position]] = {}
    for p in account.positions:
        if p.contract.underlying != config.ticker or p.contract.expiration <= as_of_date:
            continue  # today's expirations are handled by settlement instead
        groups.setdefault((p.strategy_tag, p.contract.expiration), []).append(p)

    for (strategy_tag, _expiration), positions in groups.items():
        entry_credit = 0.0
        current_cost_to_close = 0.0
        for p in positions:
            mid = (p.contract.bid + p.contract.ask) / 2
            if p.quantity < 0:  # short leg: contributed credit at entry, costs money to close
                entry_credit += p.average_open_price * 100 * abs(p.quantity)
                current_cost_to_close += mid * 100 * abs(p.quantity)
            else:  # long leg: cost debit at entry, returns money on close
                entry_credit -= p.average_open_price * 100 * p.quantity
                current_cost_to_close -= mid * 100 * p.quantity

        if entry_credit <= 0:
            continue  # not a net-credit position (shouldn't happen for our strategies); skip

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
