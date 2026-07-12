"""Long/flat trend-following backtest for the underlying stock itself --
no options at all. Built to answer a direct question: does simply buying
and holding the underlying while its trend is up outperform the
options credit-spread strategies (backtest/engine.py, intraday_engine.py)?

Deliberately NOT built on the options BrokerClient/OrderLeg/OptionContract
machinery -- a stock position is a structurally simpler instrument (no
strikes, expirations, or Greeks), and forcing it through option-shaped
abstractions would add complexity without benefit. Reuses the same
trend_signal regime filter as the options strategies for a fair,
apples-to-apples comparison of "same regime read, different instrument."

Long-only, matching this project's moderate-risk/no-undefined-risk mandate
from the outset -- a long stock position's max loss is bounded by its own
value (can't lose more than invested), but short stock has unbounded loss
and isn't offered here. Position size and the exit stop are both derived
from ATR (average true range), the standard way to size a stock position
by "how much room does this trade need before it's wrong," rather than
from options premium math which doesn't apply here.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pandas as pd

from robinhood_bot.ledger.store import Ledger
from robinhood_bot.strategy.signals import Trend, trend_signal

TREND_FAST, TREND_SLOW = 20, 50
ATR_WINDOW = 14
MIN_HISTORY_DAYS = max(TREND_SLOW, ATR_WINDOW) + 1


@dataclass
class StockBacktestConfig:
    ticker: str
    starting_cash: float = 100_000
    risk_per_trade_pct: float = 2.0     # % of equity risked per position, sized via the ATR stop distance
    stop_atr_multiple: float = 2.0      # stop-loss distance below entry, in multiples of ATR
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.0           # fraction of price, worse for the trader on both entry and exit


@dataclass
class StockTrade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    exit_reason: str            # "trend_exit" | "stop_loss"
    pnl: float


@dataclass
class StockBacktestResult:
    run_id: str
    ticker: str
    final_equity: float
    equity_curve: list[dict]
    trades: list[StockTrade]


def _atr(df: pd.DataFrame, window: int = ATR_WINDOW) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.rolling(window).mean()


def run_stock_backtest(
    price_df: pd.DataFrame,
    config: StockBacktestConfig,
    ledger: Ledger,
    run_id: str | None = None,
) -> StockBacktestResult:
    run_id = run_id or f"stock_backtest_{config.ticker}_{uuid.uuid4().hex[:8]}"
    mode = "backtest"

    if len(price_df) < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Need at least {MIN_HISTORY_DAYS} days of price history for "
            f"trend/ATR warmup; got {len(price_df)}."
        )

    atr = _atr(price_df)

    cash = config.starting_cash
    shares = 0
    entry_price = 0.0
    entry_date = None
    stop_price = 0.0
    trades: list[StockTrade] = []

    for i in range(MIN_HISTORY_DAYS, len(price_df)):
        today = price_df.index[i]
        close = float(price_df["Close"].iloc[i])
        low = float(price_df["Low"].iloc[i])
        current_atr = atr.iloc[i]

        # Stop-loss check first: a position already open today can be
        # stopped out intraday before we even get to the trend re-check.
        if shares > 0 and low <= stop_price:
            exit_price = stop_price * (1 - config.slippage_pct)
            proceeds = exit_price * shares - config.commission_per_trade
            cash += proceeds
            trades.append(StockTrade(
                entry_date=entry_date, exit_date=today, entry_price=entry_price,
                exit_price=exit_price, shares=shares, exit_reason="stop_loss",
                pnl=proceeds - entry_price * shares,
            ))
            shares = 0

        trend = trend_signal(price_df.iloc[: i + 1], fast=TREND_FAST, slow=TREND_SLOW)
        ledger.record_signal(run_id, mode, config.ticker, trend.value, None,
                              "long" if trend is Trend.BULLISH else "flat")

        if shares > 0 and trend is not Trend.BULLISH:
            exit_price = close * (1 - config.slippage_pct)
            proceeds = exit_price * shares - config.commission_per_trade
            cash += proceeds
            trades.append(StockTrade(
                entry_date=entry_date, exit_date=today, entry_price=entry_price,
                exit_price=exit_price, shares=shares, exit_reason="trend_exit",
                pnl=proceeds - entry_price * shares,
            ))
            shares = 0

        if shares == 0 and trend is Trend.BULLISH and pd.notna(current_atr) and current_atr > 0:
            stop_distance = current_atr * config.stop_atr_multiple
            risk_budget = cash * config.risk_per_trade_pct / 100
            candidate_shares = int(risk_budget // stop_distance)
            fill_price = close * (1 + config.slippage_pct)
            affordable_shares = int((cash - config.commission_per_trade) // fill_price)
            new_shares = max(min(candidate_shares, affordable_shares), 0)
            if new_shares > 0:
                cost = fill_price * new_shares + config.commission_per_trade
                cash -= cost
                shares = new_shares
                entry_price = fill_price
                entry_date = today
                stop_price = close - stop_distance

        equity = cash + shares * close
        ledger.record_equity_snapshot(run_id, mode, equity, cash)

    final_close = float(price_df["Close"].iloc[-1])
    final_equity = cash + shares * final_close

    return StockBacktestResult(
        run_id=run_id, ticker=config.ticker, final_equity=final_equity,
        equity_curve=ledger.equity_curve(run_id=run_id), trades=trades,
    )
