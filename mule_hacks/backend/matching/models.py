"""Immutable matching inputs, independent of SQLite, Reflex and the encoder."""

from dataclasses import dataclass, field
from typing import Literal

Vector = tuple[float, ...]
PersonalAnswer = str | frozenset[str]
ConnectionMode = Literal["similar", "different", "trait"]


@dataclass(frozen=True)
class PuzzlePiece:
    id: str
    category: str
    text: str
    embedding: Vector


@dataclass(frozen=True)
class UserMatchingData:
    user_id: int
    puzzle: tuple[PuzzlePiece, ...] = ()
    daily_questions: dict[int, Vector] = field(default_factory=dict)
    polls: dict[int, int] = field(default_factory=dict)
    groups: frozenset[int] = frozenset()
    personal: dict[str, PersonalAnswer] = field(default_factory=dict)


@dataclass(frozen=True)
class TraitRequest:
    """Select an existing answer/piece/group; matching never embeds a query."""

    category: str
    value: str
    field: str | None = None


@dataclass(frozen=True)
class PuzzleSimilarity:
    score: float | None
    matches: tuple[dict, ...] = ()
    strongest: tuple[dict, ...] = ()
    weakest: tuple[dict, ...] = ()
    unmatched_a: tuple[str, ...] = ()
    unmatched_b: tuple[str, ...] = ()
