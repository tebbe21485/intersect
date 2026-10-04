"""Reusable matching functions; importing this package never loads the model."""

from .config import MatchingConfig
from .models import PuzzlePiece, TraitRequest, UserMatchingData
from .scoring import (
    apply_connection_mode,
    calculate_cosine_similarity,
    calculate_daily_question_similarity,
    calculate_group_similarity,
    calculate_overall_similarity,
    calculate_personal_similarity,
    calculate_poll_similarity,
    calculate_puzzle_similarity,
    generate_match_reason,
    normalize_available_weights,
    rank_candidates,
    score_pair,
)

__all__ = [
    "MatchingConfig",
    "PuzzlePiece",
    "TraitRequest",
    "UserMatchingData",
    "apply_connection_mode",
    "calculate_cosine_similarity",
    "calculate_daily_question_similarity",
    "calculate_group_similarity",
    "calculate_overall_similarity",
    "calculate_personal_similarity",
    "calculate_poll_similarity",
    "calculate_puzzle_similarity",
    "generate_match_reason",
    "normalize_available_weights",
    "rank_candidates",
    "score_pair",
]
