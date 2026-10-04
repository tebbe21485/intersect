"""Authorized matching operations. Slow encoding runs outside write transactions."""

import json
from dataclasses import asdict

from .. import repository as r
from .. import validation as v
from ..errors import AppError
from .config import (
    ALGORITHM_VERSION,
    MAX_MATCH_RESULTS,
    MAX_PUZZLE_PIECES,
    PERSONAL_FIELDS,
    PUZZLE_CATEGORIES,
    MatchingConfig,
)
from .embeddings import generate_embedding, validate_embedding
from .models import TraitRequest
from .scoring import generate_match_reason, rank_candidates
from .storage import load_matching_data, save_embedding, stored_embedding


class MatchingService:
    def __init__(self, database, embedding_generator=None, config=None):
        self.database = database
        self.generate = embedding_generator or generate_embedding
        self.config = config or MatchingConfig()

    def profile(self, uid):
        uid = v.identifier(uid)
        with self.database.transaction() as c:
            r.actor(c, uid)
            return {
                "puzzlePieces": [
                    {
                        "id": str(row["piece_id"]),
                        "category": row["category"],
                        "text": row["content"],
                        "title": row["title"] or row["category"].replace("_", " ").title()[:20],
                        "description": row["content"],
                    }
                    for row in c.execute(
                        "SELECT * FROM puzzlepiecebase WHERE user_id=? ORDER BY piece_id",
                        (uid,),
                    )
                ],
                "personalAnswers": {
                    row["field"]: json.loads(row["answer_json"])
                    for row in c.execute(
                        "SELECT field,answer_json FROM personalanswerbase WHERE user_id=?",
                        (uid,),
                    )
                },
                "personalFields": PERSONAL_FIELDS,
                "puzzleCategories": list(PUZZLE_CATEGORIES),
            }

    def save_piece(self, uid, payload):
        uid = v.identifier(uid)
        category = payload.get("category")
        if category not in PUZZLE_CATEGORIES:
            raise AppError("Choose an available puzzle category.")
        text = v.text(payload.get("description", payload.get("text")), "Description", 500)
        # Keep older clients compatible while the editor supplies explicit titles.
        title = v.text(payload.get("title", category.replace("_", " ").title()[:20]), "Title", 20)
        piece_id = (
            v.identifier(payload["id"]) if payload.get("id") is not None else None
        )
        with self.database.transaction() as c:
            r.actor(c, uid)
            if piece_id:
                r.one(
                    c,
                    "SELECT 1 FROM puzzlepiecebase WHERE piece_id=? AND user_id=?",
                    (piece_id, uid),
                )
            elif (
                c.execute(
                    "SELECT COUNT(*) FROM puzzlepiecebase WHERE user_id=?", (uid,)
                ).fetchone()[0]
                >= MAX_PUZZLE_PIECES
            ):
                raise AppError(
                    f"Keep your puzzle to at most {MAX_PUZZLE_PIECES} pieces."
                )
            vector = stored_embedding(c, "puzzle", piece_id, text) if piece_id else None
        if vector is None:
            vector = validate_embedding(self.generate(text))
        with self.database.transaction(write=True) as c:
            r.actor(c, uid)
            if piece_id:
                r.one(
                    c,
                    "SELECT 1 FROM puzzlepiecebase WHERE piece_id=? AND user_id=?",
                    (piece_id, uid),
                )
                c.execute(
                    "UPDATE puzzlepiecebase SET content=?,category=?,title=?,updated_at=CURRENT_TIMESTAMP WHERE piece_id=? AND user_id=?",
                    (text, category, title, piece_id, uid),
                )
            else:
                if (
                    c.execute(
                        "SELECT COUNT(*) FROM puzzlepiecebase WHERE user_id=?", (uid,)
                    ).fetchone()[0]
                    >= MAX_PUZZLE_PIECES
                ):
                    raise AppError(
                        f"Keep your puzzle to at most {MAX_PUZZLE_PIECES} pieces."
                    )
                piece_id = c.execute(
                    "INSERT INTO puzzlepiecebase(user_id,category,content,title) VALUES(?,?,?,?)",
                    (uid, category, text, title),
                ).lastrowid
            save_embedding(c, "puzzle", piece_id, uid, text, vector)
        return {"id": str(piece_id), "category": category, "text": text, "title": title, "description": text}

    def delete_piece(self, uid, payload):
        uid, piece_id = v.identifier(uid), v.identifier(payload.get("id"))
        with self.database.transaction(write=True) as c:
            r.actor(c, uid)
            r.one(
                c,
                "SELECT 1 FROM puzzlepiecebase WHERE piece_id=? AND user_id=?",
                (piece_id, uid),
            )
            c.execute(
                "DELETE FROM embeddingbase WHERE source='puzzle' AND source_id=? AND user_id=?",
                (piece_id, uid),
            )
            c.execute(
                "DELETE FROM puzzlepiecebase WHERE piece_id=? AND user_id=?",
                (piece_id, uid),
            )
        return {"ok": True}

    def save_personal(self, uid, payload):
        uid = v.identifier(uid)
        answers = payload.get("answers")
        if not isinstance(answers, dict) or any(
            field not in PERSONAL_FIELDS for field in answers
        ):
            raise AppError("Choose available personal fields.")
        checked = {}
        for field, answer in answers.items():
            definition = PERSONAL_FIELDS[field]
            if answer is None or answer == "" or answer == []:
                checked[field] = None
            elif definition["kind"] == "categorical":
                if not isinstance(answer, str) or answer not in definition["options"]:
                    raise AppError(f"Choose an available answer for {field}.")
                checked[field] = answer
            else:
                if (
                    not isinstance(answer, list)
                    or len(answer) > len(definition["options"])
                    or any(
                        not isinstance(item, str) or item not in definition["options"]
                        for item in answer
                    )
                ):
                    raise AppError(f"Choose available answers for {field}.")
                checked[field] = sorted(set(answer))
        with self.database.transaction(write=True) as c:
            r.actor(c, uid)
            for field, answer in checked.items():
                if answer is None:
                    c.execute(
                        "DELETE FROM personalanswerbase WHERE user_id=? AND field=?",
                        (uid, field),
                    )
                else:
                    c.execute(
                        "INSERT INTO personalanswerbase(user_id,field,answer_json) VALUES(?,?,?) ON CONFLICT(user_id,field) DO UPDATE SET answer_json=excluded.answer_json,updated_at=CURRENT_TIMESTAMP",
                        (uid, field, json.dumps(answer)),
                    )
        return self.profile(uid)

    def prepare_daily_answer(self, uid, payload):
        """Validate before encoding, then application.py commits text and vector together."""
        uid, qid = v.identifier(uid), v.identifier(payload.get("questionId"))
        text = v.text(payload.get("text"), "Answer", 500)
        with self.database.transaction() as c:
            r.actor(c, uid)
            question = r.one(
                c, "SELECT status FROM dailyquestionbase WHERE thread_id=?", (qid,)
            )
            if question["status"] != "published":
                raise AppError(
                    "This activity is closed. Choose another active activity.", 409
                )
            existing = c.execute(
                "SELECT response_id FROM dailyresponsebase WHERE thread_id=? AND sender_id=?",
                (qid, uid),
            ).fetchone()
            vector = (
                stored_embedding(c, "daily", existing[0], text) if existing else None
            )
        return text, vector if vector is not None else validate_embedding(
            self.generate(text)
        )

    @staticmethod
    def trait(payload):
        if payload is None:
            return None
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("category"), str)
            or not isinstance(payload.get("value"), (str, int))
            or isinstance(payload.get("value"), bool)
        ):
            raise AppError("Choose a saved trait.")
        field = payload.get("field")
        if field is not None and (
            not isinstance(field, str) or field not in PERSONAL_FIELDS
        ):
            raise AppError("Choose an available personal field.")
        return TraitRequest(payload["category"], str(payload["value"]), field)

    def rank_in_transaction(self, c, uid, *, mode="similar", trait=None, context=None):
        r.actor(c, uid)
        user, candidates, aliases = load_matching_data(c, uid)
        selected_trait = self.trait(trait)
        # Existing activity buttons require shared evidence from that activity.
        if context:
            kind = context.get("kind")
            if kind == "similar-answer":
                qid = v.identifier(context.get("questionId"))
                if qid not in user.daily_questions:
                    raise AppError(
                        "Save an answer to this question before matching.", 409
                    )
                selected_trait, mode = (
                    TraitRequest("daily_questions", str(qid)),
                    "trait",
                )
            elif kind == "poll":
                pid = v.identifier(context.get("pollId"))
                if pid not in user.polls:
                    raise AppError(
                        "Answer this poll before matching through it.", 409
                    )
                selected_trait, mode = TraitRequest("polls", str(pid)), "trait"
        try:
            results = rank_candidates(
                user, candidates, mode=mode, trait=selected_trait, config=self.config
            )
        except ValueError as error:
            raise AppError(str(error)) from None
        groups = {
            str(row["thread_id"]): row["title"]
            for row in c.execute(
                "SELECT thread_id,title FROM threadbase WHERE approval='approved'"
            )
        }
        for result in results:
            result["shared_anchors"] = [
                f"Shared group: {groups.get(anchor.removeprefix('Shared group: '), 'group')}"
                if anchor.startswith("Shared group: ")
                else anchor
                for anchor in result["shared_anchors"]
            ]
            result["match_reason"] = generate_match_reason(
                result["shared_anchors"], mode
            )
            if selected_trait is not None:
                result["requested_trait"] = asdict(selected_trait)
            result["alias"] = aliases[result["user_id"]]
            result["algorithm"] = ALGORITHM_VERSION
        return results

    def candidates(self, uid, *, mode="similar", trait=None, limit=20):
        uid = v.identifier(uid)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_MATCH_RESULTS
        ):
            raise AppError(f"Request between 1 and {MAX_MATCH_RESULTS} results.")
        with self.database.transaction() as c:
            results = self.rank_in_transaction(c, uid, mode=mode, trait=trait)
        return {"matches": results[:limit], "algorithm": ALGORITHM_VERSION}

    def connect(self, c, uid, payload):
        results = self.rank_in_transaction(
            c,
            uid,
            mode=payload.get("mode", "similar"),
            trait=payload.get("trait"),
            context=payload if payload.get("kind") != "match" else None,
        )
        peer = (
            v.identifier(payload["userId"])
            if payload.get("userId") is not None
            else None
        )
        selected = next(
            (result for result in results if peer is None or result["user_id"] == peer),
            None,
        )
        if selected is None:
            raise AppError(
                "No available connection meets these requirements yet. Try another mode or add more answers.",
                409,
            )
        peer = selected["user_id"]
        a, b = sorted((uid, peer))
        tid = c.execute(
            "INSERT INTO directthreadbase(sender_id,receiver_id,source,shared) VALUES(?,?,?,?)",
            (a, b, "Connection matching", selected["match_reason"]),
        ).lastrowid
        explanation = {
            **selected,
            "configured_weights": asdict(self.config),
            "requested_trait": selected.get("requested_trait"),
        }
        c.execute(
            "INSERT INTO matchdecisionbase(thread_id,requester_id,candidate_id,algorithm,mode,score,explanation_json) VALUES(?,?,?,?,?,?,?)",
            (
                tid,
                uid,
                peer,
                ALGORITHM_VERSION,
                selected["connection_mode"],
                selected["overall_similarity"],
                json.dumps(explanation, allow_nan=False),
            ),
        )
        return {
            "connection": r.connection(c, uid, tid),
            "completed": bool(
                c.execute(
                    "SELECT 1 FROM directmessagebase WHERE sender_id=? LIMIT 1", (uid,)
                ).fetchone()
            ),
            "match": selected,
        }

    def backfill(self):
        """Explicit repair of old/missing vectors, never a side effect of ranking."""
        with self.database.transaction() as c:
            rows = [
                ("puzzle", row["piece_id"], row["user_id"], row["content"])
                for row in c.execute("SELECT * FROM puzzlepiecebase")
            ]
            rows += [
                ("daily", row["response_id"], row["sender_id"], row["content"])
                for row in c.execute("SELECT * FROM dailyresponsebase")
            ]
            pending = [
                row
                for row in rows
                if row[3].strip()
                and stored_embedding(c, row[0], row[1], row[3]) is None
            ]
        saved = 0
        for source, record_id, uid, text in pending:
            vector = validate_embedding(self.generate(text))
            table, key = (
                ("puzzlepiecebase", "piece_id")
                if source == "puzzle"
                else ("dailyresponsebase", "response_id")
            )
            with self.database.transaction(write=True) as c:
                current = c.execute(
                    f"SELECT content FROM {table} WHERE {key}=?", (record_id,)
                ).fetchone()
                if (
                    current
                    and current[0] == text
                    and stored_embedding(c, source, record_id, text) is None
                ):
                    save_embedding(c, source, record_id, uid, text, vector)
                    saved += 1
        empty = sum(not row[3].strip() for row in rows)
        return {
            "embedded": saved,
            "alreadyCurrent": len(rows) - len(pending) - empty,
            "skippedEmpty": empty,
        }
