"""Shared, fail-closed diagnostics contract for strategy decisions.

Expected returns are signed decimal fractions: positive means an upward/long
edge and negative means a downward/short edge.  Missing values are represented
by ``None`` and never silently converted to zero.
"""

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class StrategyDiagnostics:
    """Decision diagnostics shared by strategy, simulation, and live paths."""

    expected_return: Optional[float] = None
    confidence: Optional[float] = None
    signal_strength: Optional[float] = None
    fee_rate: Optional[float] = None
    fee_adjusted_expected_return: Optional[float] = None
    report_only: bool = False
    unavailable_reasons: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        """Whether the required directional return diagnostic is valid."""
        return self.expected_return is not None and not self.unavailable_reasons

    @property
    def valid(self) -> bool:
        """Whether all supplied numeric diagnostics are finite and in range."""
        values = (self.expected_return, self.confidence, self.signal_strength,
                  self.fee_rate, self.fee_adjusted_expected_return)
        try:
            finite = all(value is None or isfinite(float(value)) for value in values)
        except (TypeError, ValueError):
            finite = False
        if not finite:
            return False
        return (
            (self.confidence is None or 0.0 <= self.confidence <= 1.0)
            and (self.fee_rate is None or self.fee_rate >= 0.0)
        )

    def for_action(self, action: str, min_confidence: float = 0.0,
                   min_expected_return: float = 0.0,
                   fee_rate: Optional[float] = None) -> Dict[str, Any]:
        """Return an auditable gate decision for ``buy`` or ``sell``.

        Simulation may record this decision while continuing in report-only
        mode. Live callers must require ``allowed`` before submitting orders.
        """
        reasons = list(self.unavailable_reasons)
        if action not in {"buy", "sell"}:
            reasons.append("unsupported_action")
        if not self.valid:
            reasons.append("invalid_diagnostic")
        if not self.available:
            reasons.append("expected_return_unavailable")
        if self.confidence is None:
            reasons.append("confidence_unavailable")
        elif self.confidence < min_confidence:
            reasons.append("confidence_below_threshold")

        effective_fee = self.fee_rate if fee_rate is None else fee_rate
        if effective_fee is None:
            effective_fee = 0.0
        signed_return = self.expected_return
        adjusted = self.fee_adjusted_expected_return
        if adjusted is None and signed_return is not None:
            adjusted = signed_return - effective_fee if action == "buy" else signed_return + effective_fee

        if adjusted is None:
            reasons.append("fee_adjusted_return_unavailable")
        elif action == "buy" and adjusted <= min_expected_return:
            reasons.append("non_positive_buy_return")
        elif action == "sell" and adjusted >= -min_expected_return:
            reasons.append("non_positive_sell_return")

        return {
            "allowed": not reasons,
            "action": action,
            "expected_return": signed_return,
            "fee_adjusted_expected_return": adjusted,
            "confidence": self.confidence,
            "signal_strength": self.signal_strength,
            "fee_rate": effective_fee,
            "report_only": self.report_only,
            "reasons": tuple(dict.fromkeys(reasons)),
        }

    def as_dict(self) -> Dict[str, Any]:
        """Serialize diagnostics without replacing unavailable values."""
        return {
            "expected_return": self.expected_return,
            "confidence": self.confidence,
            "signal_strength": self.signal_strength,
            "fee_rate": self.fee_rate,
            "fee_adjusted_expected_return": self.fee_adjusted_expected_return,
            "available": self.available,
            "valid": self.valid,
            "report_only": self.report_only,
            "unavailable_reasons": self.unavailable_reasons,
        }

    @classmethod
    def from_signal(cls, signal: Dict[str, Any], *, fee_rate: Optional[float] = None,
                    report_only: bool = False) -> "StrategyDiagnostics":
        """Build the contract from legacy signal payloads safely."""
        raw = signal.get("diagnostics")
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, dict):
            signal = {**signal, **raw}
        expected = signal.get("expected_return")
        if expected is None:
            expected = signal.get("expected_return_percentage")
            if expected is not None:
                try:
                    expected = float(expected) / 100.0
                except (TypeError, ValueError):
                    pass
        fee = signal.get("fee_rate", fee_rate)
        def number(value: Any) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        reasons = list(signal.get("unavailable_reasons", ()))  # type: list[str]
        if expected is not None and number(expected) is None:
            reasons.append("expected_return_invalid")
        return cls(
            expected_return=number(expected),
            confidence=number(signal.get("model_confidence", signal.get("confidence"))),
            signal_strength=number(signal.get("signal_strength")),
            fee_rate=number(fee),
            fee_adjusted_expected_return=number(signal.get("fee_adjusted_expected_return")),
            report_only=report_only,
            unavailable_reasons=tuple(reasons),
        )
