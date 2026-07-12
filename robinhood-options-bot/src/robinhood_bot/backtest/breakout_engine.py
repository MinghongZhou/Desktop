"""Long-only Donchian breakout + chandelier trailing-stop backtest.

Built specifically to fix what the SMA-crossover trend strategy
(stock_engine.py) got wrong: a real backtest (SPY plus 7 semiconductor
names, ~8-year window including the 2020 crash and 2022 bear market)
showed that strategy losing to buy-and-hold on BOTH CAGR and Sharpe for
every single ticker, 0/8. The likely cause is structural, not tunable --
a lagging moving-average crossover gets whipsawed in chop and its signal
lag causes it to miss the sharpest recovery days after a drawdown, which
is where a disproportionate share of long-run equity returns comes from.
Its exit (a stop fixed at entry) also caps upside the same way its entry
caps downside: symmetrically, which is the wrong shape for a strategy
whose whole point is supposed to be capturing large trends.

This strategy fixes both ends:
- Entry requires actual price strength (a new N-day high), not just two
  averages crossing -- the classic Donchian/"turtle" breakout entry,
  chosen because it only fires on genuine momentum, not noise around a
  crossover point.
- The stop trails UP from the highest close since entry (a "chandelier"
  stop) instead of staying fixed at the entry price. A winning trade's
  stop keeps rising with it, letting the position ride as long as the
  trend holds, only locking in an exit once price actually reverses by
  a meaningful multiple of its own volatility -- rather than exiting on
  the first minor pullback the way a tight fixed stop or an SMA
  crossover both do.

Same long-only constraint as stock_engine.py (bounded max loss, no
undefined-risk short exposure), same ATR-based position sizing logic,
and deliberately not built on the options BrokerClient machinery for the
same reason stock_engine.py isn't.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pandas as pd

from robinhood_bot.backtest.stock_engine import ATR_WINDOW, _atr
from robinhood_bot.ledger.store import Ledger

ENTRY_WINDOW = 55  # Donchian channel lookback for the breakout high -- the classic "turtle" long entry
MIN_HISTORY_DAYS = max(ENTRY_WINDOW, ATR_WINDOW) + 1


@dataclass
class BreakoutBacktestConfig:
    ticker: str
    starting_cash: float = 100_000
    entry_window: int = ENTRY_WINDOW
    risk_per_trade_pct: float = 2.0     # % of equity risked per position, sized via the initial ATR stop distance
    stop_atr_multiple: float = 3.0      # chandelier trailing-stop distance below the highest close since entry
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.0


@dataclass
class BreakoutTrade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    pnl: float


@dataclass
class BreakoutBacktestResult:
    run_id: str
    ticker: str
    final_equity: float
    equity_curve: list[dict]
    trades: list[BreakoutTrade]


def run_breakout_backtest(
    price_df: pd.DataFrame,
    config: BreakoutBacktestConfig,
    ledger: Ledger,
    run_id: str | None = None,
) -> BreakoutBacktestResult:
    run_id = run_id or f"breakout_backtest_{config.ticker}_{uuid.uuid4().hex[:8]}"
    mode = "backtest"
    min_history = max(config.entry_window, ATR_WINDOW) + 1

    if len(price_df) < min_history:
        raise ValueError(
            f"Need at least {min_history} days of price history for "
            f"breakout/ATR warmup; got {len(price_df)}."
        )

    atr = _atr(price_df)
    # Prior N-day high, excluding today -- so today's close is compared
    # against the channel that existed *before* today, not one today's
    # own high has already widened.
    donchian_high = price_df["High"].rolling(config.entry_window).max().shift(1)

    cash = config.starting_cash
    shares = 0
    entry_price = 0.0
    entry_date = None
    highest_close_since_entry = 0.0
    stop_price = 0.0
    trades: list[BreakoutTrade] = []

    for i in range(min_history, len(price_df)):
        today = price_df.index[i]
        close = float(price_df["Close"].iloc[i])
        low = float(price_df["Low"].iloc[i])
        current_atr = atr.iloc[i]

        if shares > 0:
            highest_close_since_entry = max(highest_close_since_entry, close)
            if pd.notna(current_atr) and current_atr > 0:
                # Trail up only -- never loosen a stop that's already tightened.
                new_stop = highest_close_since_entry - current_atr * config.stop_atr_multiple
                stop_price = max(stop_price, new_stop)

            if low <= stop_price:
                exit_price = stop_price * (1 - config.slippage_pct)
                proceeds = exit_price * shares - config.commission_per_trade
                cash += proceeds
                trades.append(BreakoutTrade(
                    entry_date=entry_date, exit_date=today, entry_price=entry_price,
                    exit_price=exit_price, shares=shares,
                    pnl=proceeds - entry_price * shares,
                ))
                shares = 0

        ledger.record_signal(
            run_id, mode, config.ticker,
            "bullish" if shares > 0 else "neutral", None,
            "long" if shares > 0 else "flat",
        )

        if shares == 0 and pd.notna(current_atr) and current_atr > 0 and pd.notna(donchian_high.iloc[i]):
            if close > donchian_high.iloc[i]:
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
                    highest_close_since_entry = close
                    stop_price = close - stop_distance

        equity = cash + shares * close
        ledger.record_equity_snapshot(run_id, mode, equity, cash)

    final_close = float(price_df["Close"].iloc[-1])
    final_equity = cash + shares * final_close

    return BreakoutBacktestResult(
        run_id=run_id, ticker=config.ticker, final_equity=final_equity,
        equity_curve=ledger.equity_curve(run_id=run_id), trades=trades,
    )
