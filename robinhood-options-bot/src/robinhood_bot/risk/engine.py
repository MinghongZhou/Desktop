"""The gate every proposed trade must pass through before an order is placed.

Holds state across calls (peak equity, today's starting equity, halt
flags) because drawdown and daily-loss limits are inherently stateful --
they compare "now" to "earlier," which a single Account snapshot can't
tell you on its own. The execution loop is responsible for calling
`mark_new_trading_day` once per session and `update_equity` after every
fill/mark so that state stays current.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from robinhood_bot.broker.base import Account, OrderLeg
from robinhood_bot.config import RiskSettings
from robinhood_bot.logging_setup import get_logger
from robinhood_bot.risk.portfolio_greeks import add, incremental_greeks, portfolio_greeks, scale
from robinhood_bot.risk.position_sizing import (
    UndefinedRiskError,
    contracts_for_risk_budget,
    estimate_max_loss_per_unit,
)

log = get_logger(__name__)


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str | None
    suggested_quantity: int
    max_loss_per_unit: float | None = None


class RiskEngine:
    def __init__(self, settings: RiskSettings):
        self._settings = settings
        self._peak_equity: float | None = None
        self._daily_start_equity: float | None = None
        self._current_day: date | None = None
        self._drawdown_halted = False
        self._kill_switch_active = False

    def export_state(self) -> dict:
        """Serializes peak equity / daily baseline / halt flags for
        persistence across process restarts -- see
        execution/state_persistence.py. Settings themselves aren't part of
        this (they come from config, not saved state)."""
        return {
            "peak_equity": self._peak_equity,
            "daily_start_equity": self._daily_start_equity,
            "current_day": self._current_day.isoformat() if self._current_day else None,
            "drawdown_halted": self._drawdown_halted,
            "kill_switch_active": self._kill_switch_active,
        }

    def import_state(self, state: dict) -> None:
        self._peak_equity = state["peak_equity"]
        self._daily_start_equity = state["daily_start_equity"]
        self._current_day = date.fromisoformat(state["current_day"]) if state["current_day"] else None
        self._drawdown_halted = state["drawdown_halted"]
        self._kill_switch_active = state["kill_switch_active"]

    # -- state transitions, driven by the execution loop --

    def mark_new_trading_day(self, today: date, equity: float) -> None:
        """Resets the daily-loss baseline. Does NOT clear a drawdown halt or
        the kill switch -- those require an explicit human review/clear,
        per the plan's go/no-go gates."""
        self._current_day = today
        self._daily_start_equity = equity
        self._bump_peak(equity)

    def update_equity(self, equity: float) -> None:
        """Call after every fill/mark so drawdown state reflects reality."""
        self._bump_peak(equity)
        if self._peak_equity:
            drawdown_pct = (self._peak_equity - equity) / self._peak_equity * 100
            if drawdown_pct >= self._settings.drawdown_circuit_breaker_pct and not self._drawdown_halted:
                log.warning(
                    "risk.drawdown_circuit_breaker_tripped",
                    drawdown_pct=round(drawdown_pct, 2),
                    peak_equity=self._peak_equity,
                    equity=equity,
                )
                self._drawdown_halted = True

    def _bump_peak(self, equity: float) -> None:
        if self._peak_equity is None or equity > self._peak_equity:
            self._peak_equity = equity

    def trip_kill_switch(self, reason: str) -> None:
        log.warning("risk.kill_switch_tripped", reason=reason)
        self._kill_switch_active = True

    def clear_drawdown_halt(self) -> None:
        self._drawdown_halted = False

    def clear_kill_switch(self) -> None:
        self._kill_switch_active = False

    @property
    def is_halted(self) -> bool:
        return self._drawdown_halted or self._kill_switch_active

    # -- the actual gate --

    def evaluate_new_trade(
        self,
        account: Account,
        proposed_legs: list[OrderLeg],
        open_position_groups: int,
        reserved_risk_capital: float,
    ) -> RiskDecision:
        """`open_position_groups` and `reserved_risk_capital` (dollars of
        max-loss already reserved by currently open strategies) are supplied
        by the caller rather than derived from `account.positions`, since
        grouping individual option legs back into strategies is the
        ledger/execution layer's job, not this one's."""
        halt_reason = self._halt_reason()
        if halt_reason:
            return RiskDecision(False, halt_reason, 0)

        if self._daily_start_equity:
            daily_pl_pct = (
                (account.equity - self._daily_start_equity) / self._daily_start_equity * 100
            )
            if daily_pl_pct <= -self._settings.daily_loss_limit_pct:
                return RiskDecision(
                    False,
                    f"Daily loss limit hit ({daily_pl_pct:.2f}% <= "
                    f"-{self._settings.daily_loss_limit_pct}%); no new entries today.",
                    0,
                )

        if open_position_groups + 1 > self._settings.max_concurrent_positions:
            return RiskDecision(
                False,
                f"Max concurrent positions reached ({open_position_groups}/"
                f"{self._settings.max_concurrent_positions}).",
                0,
            )

        try:
            max_loss_per_unit = estimate_max_loss_per_unit(proposed_legs)
        except UndefinedRiskError as exc:
            return RiskDecision(False, str(exc), 0)

        per_trade_budget = account.equity * self._settings.max_risk_per_trade_pct / 100
        quantity = contracts_for_risk_budget(max_loss_per_unit, per_trade_budget)
        if quantity < 1:
            return RiskDecision(
                False,
                f"Even 1 contract (${max_loss_per_unit:.2f} max loss) exceeds the "
                f"per-trade risk budget (${per_trade_budget:.2f}).",
                0,
                max_loss_per_unit,
            )

        capital_cap = account.equity * self._settings.max_capital_deployed_pct / 100
        remaining_capital = capital_cap - reserved_risk_capital
        capital_capped_quantity = contracts_for_risk_budget(max_loss_per_unit, remaining_capital)
        quantity = min(quantity, capital_capped_quantity)
        if quantity < 1:
            return RiskDecision(
                False,
                f"Capital deployment cap leaves no room for another contract "
                f"(${reserved_risk_capital:.2f} already reserved of ${capital_cap:.2f} cap).",
                0,
                max_loss_per_unit,
            )

        projected = add(portfolio_greeks(account), scale(incremental_greeks(proposed_legs), quantity))
        if abs(projected.delta) > self._settings.max_portfolio_delta:
            return RiskDecision(
                False,
                f"Projected portfolio delta {projected.delta:.1f} exceeds cap "
                f"{self._settings.max_portfolio_delta}.",
                0,
                max_loss_per_unit,
            )
        if projected.theta < self._settings.max_portfolio_theta:
            return RiskDecision(
                False,
                f"Projected portfolio theta {projected.theta:.1f} breaches floor "
                f"{self._settings.max_portfolio_theta}.",
                0,
                max_loss_per_unit,
            )
        if abs(projected.vega) > self._settings.max_portfolio_vega:
            return RiskDecision(
                False,
                f"Projected portfolio vega {projected.vega:.1f} exceeds cap "
                f"{self._settings.max_portfolio_vega}.",
                0,
                max_loss_per_unit,
            )

        return RiskDecision(True, None, quantity, max_loss_per_unit)

    def _halt_reason(self) -> str | None:
        if self._kill_switch_active:
            return "Kill switch is active."
        if self._drawdown_halted:
            return (
                f"Drawdown circuit breaker tripped (>= "
                f"{self._settings.drawdown_circuit_breaker_pct}% from peak equity); "
                "halted pending manual review."
            )
        return None
