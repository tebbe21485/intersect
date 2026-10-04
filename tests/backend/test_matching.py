"""Deterministic algorithm tests: no model download, database or GPU required."""

import math
import unittest

from mule_hacks.backend.matching import (
    MatchingConfig,
    PuzzlePiece,
    TraitRequest,
    UserMatchingData,
    calculate_cosine_similarity,
    calculate_daily_question_similarity,
    calculate_group_similarity,
    calculate_overall_similarity,
    calculate_personal_similarity,
    calculate_poll_similarity,
    calculate_puzzle_similarity,
    normalize_available_weights,
    rank_candidates,
    score_pair,
)
from mule_hacks.backend.matching.scoring import _best_assignment


def piece(key, vector, category="interests"):
    return PuzzlePiece(str(key), category, "A short puzzle piece", tuple(vector))


class MatchingTests(unittest.TestCase):
    def test_cosine_normalization_and_invalid_vectors(self):
        self.assertEqual(calculate_cosine_similarity((2, 0), (5, 0)), 1)
        self.assertEqual(calculate_cosine_similarity((1, 0), (0, 1)), 0)
        self.assertEqual(calculate_cosine_similarity((1, 0), (-1, 0)), 0)
        for a, b in [
            ((), ()),
            ((0, 0), (1, 0)),
            ((1,), (1, 0)),
            ((math.nan,), (1,)),
            ((math.inf,), (1,)),
        ]:
            with self.subTest(a=a), self.assertRaises(ValueError):
                calculate_cosine_similarity(a, b)

    def test_identical_users_all_categories_and_weights(self):
        data = {
            "puzzle": (piece(1, (1, 0)), piece(2, (0, 1))),
            "daily_questions": {1: (1, 0)},
            "polls": {1: 2},
            "groups": frozenset({1, 2}),
            "personal": {
                "status": "student",
                "hobbies": frozenset({"robotics", "coding"}),
            },
        }
        a, b = UserMatchingData(1, **data), UserMatchingData(2, **data)
        result = score_pair(a, b)
        self.assertEqual(result["overall_similarity"], 1)
        self.assertTrue(all(x == 1 for x in result["category_scores"].values()))
        self.assertEqual(
            result["effective_weights"],
            {"puzzle": 0.4, "questions_polls": 0.2, "groups": 0.2, "personal": 0.2},
        )
        self.assertIn("robotics", result["shared_anchors"])
        self.assertNotIn("compatibility", result["match_reason"])

    def test_highly_different_profiles_do_not_qualify_as_different_mode(self):
        a = UserMatchingData(
            1,
            puzzle=(piece(1, (1, 0)),),
            polls={1: 1},
            groups=frozenset({1}),
            personal={"status": "student"},
        )
        b = UserMatchingData(
            2,
            puzzle=(piece(2, (0, 1)),),
            polls={1: 2},
            groups=frozenset({2}),
            personal={"status": "professional"},
        )
        self.assertEqual(score_pair(a, b)["overall_similarity"], 0)
        self.assertEqual(rank_candidates(a, [b], mode="different"), [])

    def test_missing_sections_redistribute_proportionally(self):
        overall, weights, subweights = calculate_overall_similarity(
            {
                "puzzle": 0.8,
                "daily_questions": 0.6,
                "polls": None,
                "groups": None,
                "personal": 1,
            }
        )
        self.assertEqual(
            weights,
            {"puzzle": 0.5, "questions_polls": 0.25, "groups": 0, "personal": 0.25},
        )
        self.assertEqual(subweights, {"daily_questions": 1, "polls": 0})
        self.assertAlmostEqual(overall, 0.8)
        overall, weights, _ = calculate_overall_similarity({})
        self.assertIsNone(overall)
        self.assertEqual(sum(weights.values()), 0)
        self.assertEqual(
            rank_candidates(UserMatchingData(1), [UserMatchingData(2)]), []
        )

    def test_users_with_only_puzzle_data(self):
        a, b = (
            UserMatchingData(1, puzzle=(piece(1, (1, 0)),)),
            UserMatchingData(2, puzzle=(piece(2, (0.8, 0.6)),)),
        )
        result = score_pair(a, b)
        self.assertAlmostEqual(result["overall_similarity"], 0.8)
        self.assertEqual(result["effective_weights"]["puzzle"], 1)
        self.assertIsNone(result["category_scores"]["polls"])
        self.assertEqual(len(rank_candidates(a, [b], mode="similar")), 1)

    def test_one_strong_piece_cannot_dominate_or_be_reused(self):
        a = (piece(1, (1, 0)), piece(2, (0, 1)), piece(3, (0, 1)), piece(4, (0, 1)))
        b = (piece(5, (1, 0)),)
        forward, reverse = (
            calculate_puzzle_similarity(a, b),
            calculate_puzzle_similarity(b, a),
        )
        self.assertEqual(forward.score, 0.25)
        self.assertEqual(reverse.score, forward.score)
        self.assertEqual(len(forward.strongest), 1)
        self.assertEqual(len(forward.unmatched_a), 3)
        # Maximum assignment is better than selecting the largest pair greedily.
        matrix = [[0.9, 0.8], [0.85, 0.1]]
        self.assertAlmostEqual(
            sum(matrix[i][j] for i, j in _best_assignment(matrix)), 1.65
        )

    def test_puzzle_weak_areas_and_missing_puzzle(self):
        result = calculate_puzzle_similarity(
            (piece(1, (1, 0)), piece(2, (0, 1))), (piece(3, (1, 0)), piece(4, (0, -1)))
        )
        self.assertEqual(result.score, 0.5)
        self.assertEqual(len(result.strongest), 1)
        self.assertEqual(len(result.weakest), 1)
        self.assertIsNone(calculate_puzzle_similarity((), (piece(1, (1, 0)),)).score)

    def test_questions_and_polls_only_use_shared_record_ids(self):
        self.assertEqual(
            calculate_daily_question_similarity(
                {1: (1, 0), 2: (0, 1)}, {1: (1, 0), 3: (1, 0)}
            ),
            1,
        )
        self.assertIsNone(calculate_daily_question_similarity({1: (1, 0)}, {2: (1, 0)}))
        self.assertEqual(
            calculate_poll_similarity({1: 1, 2: 2, 3: 9}, {1: 1, 2: 3, 4: 9}), 0.5
        )
        self.assertIsNone(calculate_poll_similarity({1: 1}, {2: 1}))
        overall, _, sub = calculate_overall_similarity(
            {"daily_questions": 1, "polls": 0}
        )
        self.assertAlmostEqual(overall, 0.7)
        self.assertEqual(sub, {"daily_questions": 0.7, "polls": 0.3})
        self.assertEqual(calculate_overall_similarity({"polls": 1})[0], 1)

    def test_jaccard_groups_personal_and_missing_answers(self):
        self.assertEqual(
            calculate_group_similarity(
                {"Coding", "Music", "Gaming"}, {"Coding", "Music", "Art"}
            ),
            0.5,
        )
        self.assertIsNone(calculate_group_similarity(set(), set()))
        self.assertEqual(calculate_group_similarity({1}, set()), 0)
        self.assertEqual(
            calculate_personal_similarity(
                {
                    "status": "student",
                    "hobbies": frozenset({"art", "music"}),
                    "unused": "x",
                },
                {"status": "student", "hobbies": frozenset({"music"})},
            ),
            0.75,
        )
        self.assertIsNone(
            calculate_personal_similarity(
                {"hobbies": frozenset()}, {"hobbies": frozenset({"art"})}
            )
        )
        self.assertIsNone(
            calculate_personal_similarity({"status": "student"}, {"age_range": "18-24"})
        )

    def test_different_mode_needs_anchor_and_ranks_near_middle(self):
        a = UserMatchingData(1, puzzle=(piece(1, (1, 0)),), groups=frozenset({1}))
        # .6 and .4 overall: both have a shared group and differing puzzle topics.
        b = UserMatchingData(
            2, puzzle=(piece(2, (0.4, math.sqrt(0.84))),), groups=frozenset({1})
        )
        c = UserMatchingData(
            3, puzzle=(piece(3, (0.1, math.sqrt(0.99))),), groups=frozenset({1})
        )
        ranked = rank_candidates(a, [b, c], mode="different")
        self.assertEqual(len(ranked), 2)
        self.assertTrue(all(x["shared_anchors"] for x in ranked))
        no_anchor = UserMatchingData(
            4, puzzle=(piece(4, (0.6, 0.8)),), groups=frozenset({2})
        )
        self.assertAlmostEqual(score_pair(a, no_anchor)["overall_similarity"], 0.4)
        self.assertEqual(rank_candidates(a, [no_anchor], mode="different"), [])

    def test_similar_threshold_and_deterministic_order(self):
        a = UserMatchingData(1, polls={1: 1, 2: 1, 3: 1, 4: 1})
        b = UserMatchingData(2, polls={1: 1, 2: 1, 3: 1, 4: 2})
        c = UserMatchingData(3, polls={1: 1, 2: 1, 3: 1, 4: 1})
        d = UserMatchingData(4, polls={1: 1, 2: 1, 3: 2, 4: 2})
        self.assertEqual(
            [x["user_id"] for x in rank_candidates(a, [d, b, c, a, c])], [3, 2]
        )

    def test_specific_trait_is_a_hard_filter_not_a_bonus(self):
        a = UserMatchingData(
            1,
            puzzle=(piece(1, (1, 0)),),
            personal={"hobbies": frozenset({"robotics"}), "status": "student"},
        )
        b = UserMatchingData(
            2,
            puzzle=(piece(2, (1, 0)),),
            personal={"hobbies": frozenset({"coding"}), "status": "student"},
        )
        c = UserMatchingData(
            3,
            puzzle=(piece(3, (0, 1)),),
            personal={"hobbies": frozenset({"robotics"}), "status": "professional"},
        )
        trait = TraitRequest("personal", "robotics", "hobbies")
        result = rank_candidates(a, [b, c], mode="trait", trait=trait)
        self.assertEqual([x["user_id"] for x in result], [3])
        self.assertEqual(result[0]["trait_similarity"], 1)
        self.assertLess(result[0]["overall_similarity"], 0.75)
        self.assertEqual(
            [
                x["user_id"]
                for x in rank_candidates(
                    a, [b, c], mode="trait", trait=TraitRequest("puzzle", "1")
                )
            ],
            [2],
        )
        for selected in [
            None,
            TraitRequest("puzzle", "99"),
            TraitRequest("personal", "music", "hobbies"),
            TraitRequest("groups", "1"),
        ]:
            with self.subTest(trait=selected), self.assertRaises(ValueError):
                rank_candidates(a, [], mode="trait", trait=selected)

    def test_tuning_and_validation(self):
        config = MatchingConfig(
            puzzle_weight=0,
            question_poll_weight=1,
            group_weight=0,
            personal_weight=0,
            poll_subweight=1,
            daily_question_subweight=0,
            similar_min=0.5,
        )
        a, b = (
            UserMatchingData(1, polls={1: 1, 2: 1}),
            UserMatchingData(2, polls={1: 1, 2: 2}),
        )
        self.assertEqual(
            rank_candidates(a, [b], config=config)[0]["overall_similarity"], 0.5
        )
        for kwargs in [
            {"puzzle_weight": -1},
            {"trait_min": 1.1},
            {"similar_min": 0.9, "similar_max": 0.8},
            {"poll_subweight": 0, "daily_question_subweight": 0},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MatchingConfig(**kwargs)
        with self.assertRaises(ValueError):
            normalize_available_weights({"puzzle": math.nan}, {"puzzle": 1})
        with self.assertRaises(ValueError):
            rank_candidates(a, [], mode="unknown")
