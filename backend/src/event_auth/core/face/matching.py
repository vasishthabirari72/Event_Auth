import math
from collections.abc import Sequence, Set
from dataclasses import dataclass
from uuid import UUID

from event_auth.core.face.contracts import Band, Match, Template


@dataclass(frozen=True)
class Thresholds:
    medium: float
    high: float

    def __post_init__(self) -> None:
        if not (-1 <= self.medium < self.high <= 1):
            raise ValueError("Thresholds must satisfy -1 <= medium < high <= 1")


def normalize(vector: Sequence[float]) -> tuple[float, ...]:
    if not vector or not all(math.isfinite(v) for v in vector):
        raise ValueError("Embedding must be nonempty and finite")
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Embedding must have a finite nonzero norm")
    return tuple(v / norm for v in vector)


def identify(
    query: Sequence[float],
    templates: Sequence[Template],
    candidate_ids: Set[UUID],
    model_version: str,
    thresholds: Thresholds,
) -> Match:
    unit = normalize(query)
    scores: dict[UUID, float] = {}
    for template in templates:
        if template.member_id not in candidate_ids or template.model_version != model_version:
            continue
        other = normalize(template.vector)
        if len(unit) != len(other):
            raise ValueError("Incompatible embedding dimensions")
        score = max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(unit, other, strict=True))))
        scores[template.member_id] = max(scores.get(template.member_id, -1.0), score)
    if not scores:
        return Match(None, None, Band.NO_MATCH)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    member_id, score = ranked[0]
    # Identical best scores from different members must not pick an arbitrary identity.
    if score < thresholds.medium or (len(ranked) > 1 and abs(score - ranked[1][1]) < 1e-9):
        return Match(None, score, Band.NO_MATCH)
    return Match(member_id, score, Band.HIGH if score >= thresholds.high else Band.MEDIUM)
