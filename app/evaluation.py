"""Shared offline evaluation helpers and live token budget guard."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenBudgetGuard:
    budget: int
    used: int = 0
    estimate_per_case: int = 0

    def can_start(self, estimate: int | None = None) -> bool:
        if self.used >= self.budget:
            return False
        expected = self.estimate_per_case if estimate is None else max(0, estimate)
        return self.used + expected <= self.budget

    def record(self, tokens: int) -> None:
        self.used += max(0, int(tokens))

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.used)
