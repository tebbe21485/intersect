"""Pure, deterministic scoring. No encoding, database writes or identity reads.

Semantic overlap describes topics, not agreement or compatibility. A future
stance evaluator can replace the semantic comparator without changing storage.
"""

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from statistics import mean

from .config import PERSONAL_ANCHOR_FIELDS, MatchingConfig
from .models import PuzzleSimilarity, TraitRequest, UserMatchingData


def calculate_cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Clamp negative cosine to zero; orthogonal vectors stay zero, not 0.5."""
    if not a or len(a) != len(b):
        raise ValueError("Embedding dimensions must match and be nonempty")
    if any(not math.isfinite(x) for x in (*a, *b)):
        raise ValueError("Embeddings must be finite")
    norm_a, norm_b = math.hypot(*a), math.hypot(*b)
    if not norm_a or not norm_b:
        raise ValueError("A zero vector is not a valid embedding")
    return max(
        0.0, min(1.0, math.fsum((x / norm_a) * (y / norm_b) for x, y in zip(a, b)))
    )


def _best_assignment(matrix: list[list[float]]) -> list[tuple[int, int]]:
    """Maximum weight one-to-one assignment, O(n^3) Hungarian algorithm.

    Zero padding covers unpaired pieces. Every piece contributes at most once,
    including when several pieces repeat the same topic.
    """
    rows, cols = len(matrix), len(matrix[0])
    size = max(rows, cols)
    costs = [
        [1 - (matrix[i][j] if i < rows and j < cols else 0) for j in range(size)]
        for i in range(size)
    ]
    u, v, p, way = (
        [0.0] * (size + 1),
        [0.0] * (size + 1),
        [0] * (size + 1),
        [0] * (size + 1),
    )
    for i in range(1, size + 1):
        p[0], j0 = i, 0
        minimum, used = [math.inf] * (size + 1), [False] * (size + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, size + 1):
                if not used[j]:
                    current = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if current < minimum[j]:
                        minimum[j], way[j] = current, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return [(p[j] - 1, j - 1) for j in range(1, size + 1) if p[j] <= rows and j <= cols]


def calculate_puzzle_similarity(
    a,
    b,
    *,
    comparator: Callable = calculate_cosine_similarity,
    config: MatchingConfig | None = None,
) -> PuzzleSimilarity:
    if not a or not b:
        return PuzzleSimilarity(None)
    config = config or MatchingConfig()
    matrix = [[comparator(x.embedding, y.embedding) for y in b] for x in a]
    pairs = _best_assignment(matrix)
    matches = tuple(
        {
            "piece_a": a[i].id,
            "piece_b": b[j].id,
            "category_a": a[i].category,
            "category_b": b[j].category,
            "similarity": matrix[i][j],
        }
        for i, j in pairs
    )
    ordered = sorted(
        matches, key=lambda x: (-x["similarity"], x["piece_a"], x["piece_b"])
    )
    return PuzzleSimilarity(
        score=sum(x["similarity"] for x in matches) / max(len(a), len(b)),
        matches=matches,
        strongest=tuple(
            x for x in ordered if x["similarity"] >= config.puzzle_anchor_min
        ),
        weakest=tuple(
            sorted(
                (x for x in matches if x["similarity"] < config.puzzle_anchor_min),
                key=lambda x: x["similarity"],
            )
        ),
        unmatched_a=tuple(
            x.id for i, x in enumerate(a) if i not in {i for i, _ in pairs}
        ),
        unmatched_b=tuple(
            x.id for j, x in enumerate(b) if j not in {j for _, j in pairs}
        ),
    )


def calculate_daily_question_similarity(
    a, b, *, comparator: Callable = calculate_cosine_similarity
):
    shared = a.keys() & b.keys()
    return mean(comparator(a[key], b[key]) for key in shared) if shared else None


def calculate_poll_similarity(a, b):
    shared = a.keys() & b.keys()
    return mean(float(a[key] == b[key]) for key in shared) if shared else None


def calculate_group_similarity(a, b):
    union = set(a) | set(b)
    return len(set(a) & set(b)) / len(union) if union else None


def calculate_personal_similarity(a, b):
    scores = []
    for key in sorted(a.keys() & b.keys()):
        left, right = a[key], b[key]
        if not left or not right:
            continue
        if isinstance(left, str) and isinstance(right, str):
            scores.append(float(left == right))
        elif isinstance(left, (set, frozenset)) and isinstance(right, (set, frozenset)):
            scores.append(calculate_group_similarity(left, right))
        else:
            raise TypeError(f"Personal field {key} has inconsistent answer types")
    return mean(scores) if scores else None


def normalize_available_weights(
    scores: Mapping[str, float | None], weights: Mapping[str, float]
):
    if any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Weights must be finite and nonnegative")
    if any(
        value is not None and (not math.isfinite(value) or not 0 <= value <= 1)
        for value in scores.values()
    ):
        raise ValueError("Scores must be between zero and one or None")
    total = sum(
        weight for key, weight in weights.items() if scores.get(key) is not None
    )
    return {
        key: weight / total if total and scores.get(key) is not None else 0.0
        for key, weight in weights.items()
    }


def calculate_overall_similarity(category_scores, config: MatchingConfig | None = None):
    config = config or MatchingConfig()
    sub_scores = {
        "daily_questions": category_scores.get("daily_questions"),
        "polls": category_scores.get("polls"),
    }
    sub_weights = normalize_available_weights(
        sub_scores,
        {
            "daily_questions": config.daily_question_subweight,
            "polls": config.poll_subweight,
        },
    )
    combined = (
        sum((sub_scores[key] or 0) * weight for key, weight in sub_weights.items())
        if any(sub_weights.values())
        else None
    )
    top_scores = {
        "puzzle": category_scores.get("puzzle"),
        "questions_polls": combined,
        "groups": category_scores.get("groups"),
        "personal": category_scores.get("personal"),
    }
    effective = normalize_available_weights(top_scores, config.weights)
    overall = (
        sum((top_scores[key] or 0) * weight for key, weight in effective.items())
        if any(effective.values())
        else None
    )
    return overall, effective, sub_weights


def _anchors(a, b, puzzle):
    anchors = [f"Shared puzzle topic: {x['category_a']}" for x in puzzle.strongest]
    anchors.extend(f"Shared group: {gid}" for gid in sorted(a.groups & b.groups))
    anchors.extend(
        f"Same poll answer: {pid}"
        for pid in sorted(a.polls.keys() & b.polls.keys())
        if a.polls[pid] == b.polls[pid]
    )
    for field in sorted(PERSONAL_ANCHOR_FIELDS & a.personal.keys() & b.personal.keys()):
        left, right = a.personal[field], b.personal[field]
        if isinstance(left, frozenset) and isinstance(right, frozenset):
            anchors.extend(sorted(left & right))
    return list(dict.fromkeys(anchors))


def generate_match_reason(anchors: Sequence[str], mode: str):
    """Describe evidence, without claiming semantic overlap implies agreement."""
    if anchors:
        evidence = "; ".join(anchors[:3])
        if mode == "different":
            return (
                f"You have different answers overall, with common ground in {evidence}."
            )
        return f"Your answers overlap in {evidence}. Similar topics can still reflect different viewpoints."
    return "Your available answers have similar patterns. Explore where your viewpoints agree or differ."


def calculate_trait_similarity(
    a: UserMatchingData,
    b: UserMatchingData,
    trait: TraitRequest,
    *,
    comparator: Callable = calculate_cosine_similarity,
):
    """Require a trait from the requester's own stored answers."""
    if trait.category == "puzzle":
        selected = next((piece for piece in a.puzzle if piece.id == trait.value), None)
        if selected is None:
            raise ValueError("Select one of your saved puzzle pieces")
        return max(
            (comparator(selected.embedding, x.embedding) for x in b.puzzle),
            default=None,
        )
    if trait.category == "personal":
        own = a.personal.get(trait.field)
        if not own or (
            trait.value != own if isinstance(own, str) else trait.value not in own
        ):
            raise ValueError("Select one of your saved personal answers")
        other = b.personal.get(trait.field)
        return (
            None
            if not other
            else float(
                trait.value == other if isinstance(other, str) else trait.value in other
            )
        )
    try:
        key = int(trait.value)
    except ValueError:
        raise ValueError("Select a saved trait ID") from None
    if trait.category == "groups":
        if key not in a.groups:
            raise ValueError("Select a group you belong to")
        return float(key in b.groups)
    if trait.category == "daily_questions":
        if key not in a.daily_questions:
            raise ValueError("Select a question you have answered")
        return (
            comparator(a.daily_questions[key], b.daily_questions[key])
            if key in b.daily_questions
            else None
        )
    if trait.category == "polls":
        if key not in a.polls:
            raise ValueError("Select a poll you have answered")
        return float(a.polls[key] == b.polls[key]) if key in b.polls else None
    raise ValueError("Unknown trait category")


def apply_connection_mode(
    result: dict, mode: str, *, trait_score=None, config: MatchingConfig | None = None
):
    config = config or MatchingConfig()
    if mode not in ("similar", "different", "trait"):
        raise ValueError("Choose similar, different or trait mode")
    score = result["overall_similarity"]
    if score is None:
        return False
    if mode == "similar":
        return config.similar_min <= score <= config.similar_max
    if mode == "different":
        return config.different_min <= score <= config.different_max and bool(
            result["shared_anchors"]
        )
    return trait_score is not None and trait_score >= config.trait_min


def score_pair(
    a: UserMatchingData,
    b: UserMatchingData,
    *,
    mode="similar",
    config: MatchingConfig | None = None,
    comparator: Callable = calculate_cosine_similarity,
):
    config = config or MatchingConfig()
    puzzle = calculate_puzzle_similarity(
        a.puzzle, b.puzzle, comparator=comparator, config=config
    )
    scores = {
        "puzzle": puzzle.score,
        "daily_questions": calculate_daily_question_similarity(
            a.daily_questions, b.daily_questions, comparator=comparator
        ),
        "polls": calculate_poll_similarity(a.polls, b.polls),
        "groups": calculate_group_similarity(a.groups, b.groups),
        "personal": calculate_personal_similarity(a.personal, b.personal),
    }
    overall, effective, sub_weights = calculate_overall_similarity(scores, config)
    anchors = _anchors(a, b, puzzle)
    return {
        "user_id": b.user_id,
        "overall_similarity": overall,
        "category_scores": scores,
        "effective_weights": effective,
        "effective_subweights": sub_weights,
        "connection_mode": mode,
        "shared_anchors": anchors,
        "match_reason": generate_match_reason(anchors, mode),
        "puzzle_details": {
            "matches": list(puzzle.matches),
            "strongest": list(puzzle.strongest),
            "weakest": list(puzzle.weakest),
            "unmatched_a": list(puzzle.unmatched_a),
            "unmatched_b": list(puzzle.unmatched_b),
        },
        "comparable_counts": {
            "puzzle_a": len(a.puzzle),
            "puzzle_b": len(b.puzzle),
            "daily_questions": len(a.daily_questions.keys() & b.daily_questions.keys()),
            "polls": len(a.polls.keys() & b.polls.keys()),
            "personal": sum(
                bool(a.personal[k]) and bool(b.personal[k])
                for k in a.personal.keys() & b.personal.keys()
            ),
        },
    }


def rank_candidates(
    user: UserMatchingData,
    candidates: Iterable[UserMatchingData],
    *,
    mode="similar",
    trait: TraitRequest | None = None,
    config: MatchingConfig | None = None,
    comparator: Callable = calculate_cosine_similarity,
):
    config = config or MatchingConfig()
    # Validate before iterating, including when the candidate set is empty.
    apply_connection_mode({"overall_similarity": None}, mode, config=config)
    if mode == "trait":
        if trait is None:
            raise ValueError("Trait mode requires a selected trait")
        calculate_trait_similarity(user, user, trait, comparator=comparator)
    elif trait is not None:
        raise ValueError("A selected trait requires trait mode")
    results, seen = [], set()
    for candidate in candidates:
        if candidate.user_id == user.user_id or candidate.user_id in seen:
            continue
        seen.add(candidate.user_id)
        result = score_pair(
            user, candidate, mode=mode, config=config, comparator=comparator
        )
        trait_score = (
            calculate_trait_similarity(user, candidate, trait, comparator=comparator)
            if trait
            else None
        )
        if apply_connection_mode(result, mode, trait_score=trait_score, config=config):
            if trait:
                result["trait_similarity"] = trait_score
            results.append(result)
    if mode == "different":
        results.sort(
            key=lambda x: (
                abs(x["overall_similarity"] - config.different_target),
                -x["overall_similarity"],
                x["user_id"],
            )
        )
    else:
        results.sort(key=lambda x: (-x["overall_similarity"], x["user_id"]))
    return results
