"""Tuning for the first similarity model. Profile identity is never an input."""

from dataclasses import dataclass
from math import isfinite

PUZZLE_WEIGHT = 0.40
QUESTION_POLL_WEIGHT = 0.20
GROUP_WEIGHT = 0.20
PERSONAL_WEIGHT = 0.20
DAILY_QUESTION_SUBWEIGHT = 0.70
POLL_SUBWEIGHT = 0.30
SIMILAR_MIN = 0.75
SIMILAR_MAX = 1.00
DIFFERENT_MIN = 0.35
DIFFERENT_MAX = 0.65
DIFFERENT_TARGET = 0.50
TRAIT_MIN = 0.75
PUZZLE_ANCHOR_MIN = 0.75
MIN_PUZZLE_PIECES = 4
MAX_PUZZLE_PIECES = 8
MAX_MATCH_RESULTS = 50
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
ALGORITHM_VERSION = "similarity-v1"

PUZZLE_CATEGORIES = (
    "interests",
    "hobbies",
    "experiences",
    "favorites",
    "goals",
    "personality",
    "values",
)
# Extend this registry to collect new predefined data, without changing scoring.
# An empty answer means missing data; it is never scored as a disagreement.
PERSONAL_FIELDS = {
    "age_range": {
        "kind": "categorical",
        "options": ["under-18", "18-24", "25-34", "35-44", "45-54", "55+"],
    },
    "status": {
        "kind": "categorical",
        "options": ["student", "professional", "both", "other"],
    },
    "event_interests": {
        "kind": "multi",
        "options": [
            "technology",
            "science",
            "business",
            "art",
            "music",
            "gaming",
            "outdoors",
        ],
    },
    "hobbies": {
        "kind": "multi",
        "options": [
            "coding",
            "reading",
            "music",
            "art",
            "gaming",
            "sports",
            "outdoors",
            "cooking",
        ],
    },
    "personality": {
        "kind": "categorical",
        "options": ["introvert", "ambivert", "extrovert"],
    },
    "communication_style": {
        "kind": "categorical",
        "options": ["one-to-one", "small-group", "large-group"],
    },
    "connection_goals": {
        "kind": "multi",
        "options": ["friendship", "networking", "learning", "collaboration"],
    },
}
PERSONAL_ANCHOR_FIELDS = frozenset({"event_interests", "hobbies", "connection_goals"})


@dataclass(frozen=True)
class MatchingConfig:
    puzzle_weight: float = PUZZLE_WEIGHT
    question_poll_weight: float = QUESTION_POLL_WEIGHT
    group_weight: float = GROUP_WEIGHT
    personal_weight: float = PERSONAL_WEIGHT
    daily_question_subweight: float = DAILY_QUESTION_SUBWEIGHT
    poll_subweight: float = POLL_SUBWEIGHT
    similar_min: float = SIMILAR_MIN
    similar_max: float = SIMILAR_MAX
    different_min: float = DIFFERENT_MIN
    different_max: float = DIFFERENT_MAX
    different_target: float = DIFFERENT_TARGET
    trait_min: float = TRAIT_MIN
    puzzle_anchor_min: float = PUZZLE_ANCHOR_MIN

    def __post_init__(self):
        weights = [
            *self.weights.values(),
            self.daily_question_subweight,
            self.poll_subweight,
        ]
        if any(not isfinite(x) or x < 0 for x in weights):
            raise ValueError("Matching weights must be finite and nonnegative")
        if (
            sum(self.weights.values()) <= 0
            or self.daily_question_subweight + self.poll_subweight <= 0
        ):
            raise ValueError("Each weighting level needs a positive total")
        thresholds = [
            self.similar_min,
            self.similar_max,
            self.different_min,
            self.different_max,
            self.different_target,
            self.trait_min,
            self.puzzle_anchor_min,
        ]
        if any(not isfinite(x) or not 0 <= x <= 1 for x in thresholds):
            raise ValueError("Matching thresholds must be between zero and one")
        if (
            self.similar_min > self.similar_max
            or not self.different_min <= self.different_target <= self.different_max
        ):
            raise ValueError("Invalid matching mode ranges")

    @property
    def weights(self):
        return {
            "puzzle": self.puzzle_weight,
            "questions_polls": self.question_poll_weight,
            "groups": self.group_weight,
            "personal": self.personal_weight,
        }
