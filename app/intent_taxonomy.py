"""Gold-derived intent taxonomy and deterministic normalization."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentTaxonomy:
    major_to_minors: dict[str, tuple[str, ...]]

    @classmethod
    def from_rows(cls, rows: list[dict[str, str]]) -> "IntentTaxonomy":
        mapping: dict[str, set[str]] = {}
        for row in rows:
            major, minor = row.get("human_intent_major", "").strip(), row.get("human_intent_minor", "").strip()
            if major and minor:
                mapping.setdefault(major, set()).add(minor)
        return cls({major: tuple(sorted(minors)) for major, minors in sorted(mapping.items())})

    @property
    def majors(self) -> tuple[str, ...]:
        return tuple(self.major_to_minors)

    def normalize(self, major: str, minor: str) -> tuple[str, str] | None:
        major = self._clean(major)
        minor = self._clean(minor)
        if major not in self.major_to_minors or minor not in self.major_to_minors[major]:
            return None
        return major, minor

    def map_text(self, text: str) -> tuple[str, str] | None:
        cleaned = self._clean(text)
        exact = [(major, minor) for major, minors in self.major_to_minors.items() for minor in minors if cleaned == minor or cleaned == major]
        if exact:
            return sorted(exact, key=lambda pair: len(pair[1]), reverse=True)[0]
        matches = [(major, minor) for major, minors in self.major_to_minors.items() for minor in minors if minor in cleaned or major in cleaned]
        return sorted(matches, key=lambda pair: len(pair[1]), reverse=True)[0] if matches else None

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "")).strip().lower()
