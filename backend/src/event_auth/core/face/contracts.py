from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class Band(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NO_MATCH = "no_match"


@dataclass(frozen=True)
class Template:
    member_id: UUID
    model_version: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class Match:
    member_id: UUID | None
    score: float | None
    band: Band


class FaceEngine(Protocol):
    def embed(self, image: bytes) -> tuple[float, ...]: ...
