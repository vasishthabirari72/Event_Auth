"""Aggregate-only face evaluation; raw trial data stays in memory."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from event_auth.core.face.matching import Thresholds


@dataclass(frozen=True)
class Trial:
    genuine: bool
    correct_top: bool
    score: float | None
    impostor_score: float | None
    processing_seconds: float
    rejected_captures: int = 0

    def __post_init__(self) -> None:
        for score in (self.score, self.impostor_score):
            if score is not None and (not math.isfinite(score) or not -1 <= score <= 1):
                raise ValueError("Invalid trial score")
        if not math.isfinite(self.processing_seconds) or self.processing_seconds < 0:
            raise ValueError("Invalid trial duration")
        if self.rejected_captures < 0 or (self.correct_top and not self.genuine):
            raise ValueError("Invalid trial outcome")


@dataclass(frozen=True)
class Summary:
    genuine_attempts: int
    unknown_attempts: int
    correct_high_medium: int
    genuine_rate: float | None
    false_high: int
    false_medium: int
    rejected_captures: int
    median_seconds: float | None
    p95_seconds: float | None
    max_seconds: float | None
    accuracy_targets_met_on_sample: bool


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not 0 < fraction <= 1:
        raise ValueError("Percentile must be in (0, 1]")
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(fraction * len(values)) - 1)]


def summarize(trials: Sequence[Trial], thresholds: Thresholds) -> Summary:
    genuine = sum(t.genuine for t in trials)
    unknown = len(trials) - genuine
    correct = sum(
        t.correct_top and t.score is not None and t.score >= thresholds.medium for t in trials
    )
    false_high = sum(
        not t.correct_top and t.score is not None and t.score >= thresholds.high for t in trials
    )
    false_medium = sum(
        not t.correct_top and t.score is not None and thresholds.medium <= t.score < thresholds.high
        for t in trials
    )
    rate = correct / genuine if genuine else None
    durations = [t.processing_seconds for t in trials]
    return Summary(
        genuine,
        unknown,
        correct,
        rate,
        false_high,
        false_medium,
        sum(t.rejected_captures for t in trials),
        percentile(durations, 0.5),
        percentile(durations, 0.95),
        max(durations) if durations else None,
        bool(genuine and unknown and rate is not None and rate >= 0.9 and false_high == 0),
    )


def recommend(trials: Sequence[Trial]) -> Thresholds | None:
    """Choose candidate thresholds on calibration only; require held-out validation."""
    genuine = [t for t in trials if t.genuine]
    if not genuine or not any(not t.genuine for t in trials):
        return None
    correct_scores = sorted(
        (t.score for t in genuine if t.correct_top and t.score is not None), reverse=True
    )
    needed = math.ceil(0.9 * len(genuine))
    if len(correct_scores) < needed:
        return None  # Changing thresholds cannot repair a wrong top-ranked identity.
    medium = correct_scores[needed - 1]
    impostors = [t.impostor_score for t in trials if t.impostor_score is not None]
    impostors.extend(t.score for t in trials if not t.correct_top and t.score is not None)
    if not impostors:
        return None
    high = math.nextafter(max(medium, max(impostors)), math.inf)
    if high > 1:
        return None  # No representable safe HIGH band for this calibration sample.
    return Thresholds(medium, high)
