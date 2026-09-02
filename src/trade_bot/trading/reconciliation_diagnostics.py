"""Opt-in, deterministic diagnostics for paper reconciliation.

The recorder deliberately stores counters and timestamps only.  It never stores
payloads, credentials, or order identifiers and is inert unless enabled.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


@dataclass
class ReconciliationDiagnostics:
    enabled: bool = False
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    selected_symbols: list[str] = field(default_factory=list)
    fetches: dict[str, dict[str, Any]] = field(default_factory=dict)
    gate_outcomes: Counter = field(default_factory=Counter)
    blockers: Counter = field(default_factory=Counter)
    signals_evaluated: int = 0
    signals_generated: int = 0
    paper_intents: int = 0
    fills: int = 0

    @staticmethod
    def data_age_seconds(observed_at: datetime | None, now: datetime) -> int | None:
        """Return non-negative age in seconds, or ``None`` for invalid data."""
        if observed_at is None:
            return None
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age = int((now - observed_at).total_seconds())
        return age if age >= 0 else None

    def reset(self, selected_symbols: Iterable[str] = ()) -> None:
        if not self.enabled:
            return
        self.selected_symbols = list(selected_symbols)
        self.fetches.clear()
        self.gate_outcomes.clear()
        self.blockers.clear()
        self.signals_evaluated = self.signals_generated = 0
        self.paper_intents = self.fills = 0

    def _fetch(self, symbol: str) -> dict[str, Any]:
        return self.fetches.setdefault(symbol, {"attempts": 0, "successes": 0, "failures": 0})

    def record_fetch_attempt(self, symbol: str) -> None:
        if self.enabled:
            stats = self._fetch(symbol)
            stats["attempts"] += 1
            stats["last_attempt_at"] = self.clock()

    def record_fetch_result(self, symbol: str, success: bool, observed_at: datetime | None = None) -> None:
        if not self.enabled:
            return
        stats = self._fetch(symbol)
        stats["successes" if success else "failures"] += 1
        if success:
            observed_at = observed_at or self.clock()
            stats["observed_at"] = observed_at
            stats["last_success_at"] = observed_at

    def record_signal(self, generated: bool) -> None:
        if self.enabled:
            self.signals_evaluated += 1
            self.signals_generated += int(generated)

    def record_gate(self, outcome: str | None) -> None:
        if self.enabled:
            self.gate_outcomes[outcome or "unknown"] += 1

    def record_blocker(self, reason: str | None) -> None:
        if self.enabled:
            self.blockers[reason or "unknown"] += 1

    def record_paper_intent(self) -> None:
        if self.enabled:
            self.paper_intents += 1

    def record_fill(self) -> None:
        if self.enabled:
            self.fills += 1

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        now = now or self.clock()
        fetches: dict[str, Any] = {}
        for symbol, stats in sorted(self.fetches.items()):
            fetches[symbol] = {
                "attempts": stats["attempts"],
                "successes": stats["successes"],
                "failures": stats["failures"],
                "data_age_seconds": self.data_age_seconds(stats.get("observed_at"), now),
                "last_attempt_at": self._timestamp(stats.get("last_attempt_at")),
                "last_success_at": self._timestamp(stats.get("last_success_at")),
            }
        return {
            "enabled": True,
            "selected_symbols": list(self.selected_symbols),
            "selected_symbol_count": len(self.selected_symbols),
            "signals_evaluated": self.signals_evaluated,
            "signals_generated": self.signals_generated,
            "paper_intents": self.paper_intents,
            "fills": self.fills,
            "fetches": fetches,
            "gate_outcomes": dict(sorted(self.gate_outcomes.items())),
            "blockers": dict(sorted(self.blockers.items())),
        }
