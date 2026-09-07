"""Formatting helpers for flag-card evidence sentences.

Every detector evidence string uses Indian lakh/crore notation, matching
the register the plan's own examples use ("₹18.4L is 4.2x the median")
— an auditor reads amounts this way, not "₹1,840,000".
"""

from __future__ import annotations

_CRORE = 1_00_00_000
_LAKH = 1_00_000


def fmt_inr(amount: float | None) -> str:
    """Format a rupee amount as ₹X.XCr / ₹X.XL / ₹X,XXX."""
    if amount is None:
        return "unknown"
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= _CRORE:
        return f"{sign}₹{amount / _CRORE:.2f}Cr"
    if amount >= _LAKH:
        return f"{sign}₹{amount / _LAKH:.2f}L"
    return f"{sign}₹{amount:,.0f}"
