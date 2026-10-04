"""Transactional application operations; actor identity comes only from a session."""

from . import repository as r
from . import validation as v
from .auth import profile
from .errors import AppError
from .matching.service import MatchingService
from .matching.storage import save_embedding


class ApplicationService:
    def __init__(self, database, embedding_generator=None):
        self.database = database
        self.matching = MatchingService(database, embedding_generator)

    def load(self, uid, after_messages=None):
        if after_messages is not None:
            import json

            if not isinstance(after_messages, str) or len(after_messages) > 8192:
                raise AppError("Invalid message cursor.")
            try:
                after_messages = json.loads(after_messages)
            except ValueError:
                raise AppError("Invalid message cursor.") from None
            if not isinstance(after_messages, dict) or len(after_messages) > 100:
                raise AppError("Invalid message cursor.")
            after_messages = {
                str(v.identifier(key)): v.identifier(value)
                for key, value in after_messages.items()
            }
        with self.database.transaction() as c:
            return r.snapshot(c, v.identifier(uid), after_messages)

    def action(self, uid, method, p):
        if not isinstance(p, dict):
            raise AppError("Invalid request.")
        allowed = {
            "saveDailyAnswer",
            "voteOnPoll",
            "createConnection",
            "sendMessage",
            "joinGroup",
            "sendGroupMessage",
            "postQuestion",
            "replyToQuestion",
            "requestIdentityReveal",
            "cancelIdentityReveal",
            "sharePhone",
            "endConversation",
            "reportConnection",
            "blockConnection",
            "saveProfile",
            "proposeGroup",
            "editGroupProposal",
            "savePuzzlePiece",
            "deletePuzzlePiece",
            "savePersonalAnswers",
            "findMatches",
        }
        if not isinstance(method, str) or method not in allowed:
            raise AppError("That action is unavailable.", 404)
        uid = v.identifier(uid)
        if method == "savePuzzlePiece":
            return self.matching.save_piece(uid, p)
        if method == "deletePuzzlePiece":
            return self.matching.delete_piece(uid, p)
        if method == "savePersonalAnswers":
            return self.matching.save_personal(uid, p)
        if method == "findMatches":
            return self.matching.candidates(
                uid,
                mode=p.get("mode", "similar"),
                trait=p.get("trait"),
                limit=p.get("limit", 20),
            )
        prepared_answer = (
            self.matching.prepare_daily_answer(uid, p)
            if method == "saveDailyAnswer"
            else None
        )
        with self.database.transaction(write=True) as c:
            r.actor(c, uid)
            if method == "saveProfile":
                fields = v.profile_fields(p)
                c.execute(
                    "UPDATE userbase SET first_name=?,last_name=?,linkedin=?,phone=? WHERE user_id=?",
                    (*fields, uid),
                )
                # Changing a number requires a fresh sharing decision.
                c.execute(
                    "UPDATE consentbase SET phone_shared=0 WHERE user_id=?", (uid,)
                )
                return profile(r.actor(c, uid))
            if method == "saveDailyAnswer":
                qid = v.identifier(p.get("questionId"))
                self.active(c, "dailyquestionbase", "thread_id", qid)
                value, vector = prepared_answer
                c.execute(
                    "INSERT INTO dailyresponsebase(thread_id,sender_id,content) VALUES(?,?,?) ON CONFLICT(thread_id,sender_id) DO UPDATE SET content=excluded.content,created_at=CURRENT_TIMESTAMP",
                    (qid, uid, value),
                )
                response_id = c.execute(
                    "SELECT response_id FROM dailyresponsebase WHERE thread_id=? AND sender_id=?",
                    (qid, uid),
                ).fetchone()[0]
                save_embedding(c, "daily", response_id, uid, value, vector)
                return r.daily(c, uid, qid)
            if method == "voteOnPoll":
                pid = v.identifier(p.get("pollId"))
                choice = v.identifier(p.get("choiceId"))
                self.active(c, "pollbase", "poll_id", pid)
                r.one(
                    c,
                    "SELECT 1 FROM pollchoicebase WHERE poll_id=? AND choice_id=?",
                    (pid, choice),
                    "Choose an option from this poll.",
                )
                c.execute(
                    "INSERT INTO pollresponsebase(poll_id,sender_id,choice_id) VALUES(?,?,?) ON CONFLICT(poll_id,sender_id) DO UPDATE SET choice_id=excluded.choice_id,created_at=CURRENT_TIMESTAMP",
                    (pid, uid, choice),
                )
                return r.poll(c, uid, pid)
            if method == "createConnection":
                return self.connect(c, uid, p)
            if method in ("proposeGroup", "editGroupProposal"):
                title = v.text(p.get("name"), "Group name", 100)
                body = v.text(p.get("description", ""), "Group description", 800, False)
                if method == "proposeGroup":
                    gid = c.execute(
                        "INSERT INTO threadbase(title,body,creator_id) VALUES(?,?,?)",
                        (title, body, uid),
                    ).lastrowid
                else:
                    gid = v.identifier(p.get("groupId"))
                    r.one(
                        c,
                        "SELECT 1 FROM threadbase WHERE thread_id=? AND creator_id=?",
                        (gid, uid),
                    )
                    c.execute(
                        "UPDATE threadbase SET title=?,body=?,approval='pending',reviewer_id=NULL,decided_at=NULL,decision_reason='' WHERE thread_id=?",
                        (title, body, gid),
                    )
                return r.group(c, uid, gid)
            if method in ("joinGroup", "sendGroupMessage"):
                gid = v.identifier(p.get("groupId"))
                r.one(
                    c,
                    "SELECT 1 FROM threadbase WHERE thread_id=? AND approval='approved' AND status='open'",
                    (gid,),
                    "This group is not open for discussion.",
                )
                if method == "joinGroup":
                    c.execute(
                        "INSERT OR IGNORE INTO threadmemberbase(thread_id,user_id) VALUES(?,?)",
                        (gid, uid),
                    )
                else:
                    r.one(
                        c,
                        "SELECT 1 FROM threadmemberbase WHERE thread_id=? AND user_id=?",
                        (gid, uid),
                        "Join this group before sending a message.",
                    )
                    self.message(c, "threadmessagebase", "response_id", gid, uid, p)
                return r.group(c, uid, gid)
            if method == "postQuestion":
                category = v.text(p.get("category"), "Category", 80)
                if category not in r.CATEGORIES:
                    raise AppError("Choose an available category.")
                title = v.text(p.get("text"), "Question", 180)
                detail = v.text(p.get("detail", ""), "Context", 800, False)
                qid = c.execute(
                    "INSERT INTO boardpostbase(sender_id,category,title,detail) VALUES(?,?,?,?)",
                    (uid, category, title, detail),
                ).lastrowid
                return r.board(c, uid, qid)
            if method == "replyToQuestion":
                qid = v.identifier(p.get("questionId"))
                value = v.text(p.get("text"), "Response", 800)
                r.one(c, "SELECT 1 FROM boardpostbase WHERE post_id=?", (qid,))
                c.execute(
                    "INSERT INTO boardreplybase(post_id,sender_id,content) VALUES(?,?,?)",
                    (qid, uid, value),
                )
                return r.board(c, uid, qid)
            tid = v.identifier(p.get("connectionId"))
            _, peer = r.conversation(c, uid, tid)
            if method == "sendMessage":
                self.message(c, "directmessagebase", "msg_id", tid, uid, p)
            elif method in (
                "requestIdentityReveal",
                "cancelIdentityReveal",
                "sharePhone",
            ):
                c.execute(
                    "INSERT OR IGNORE INTO consentbase(thread_id,user_id) VALUES(?,?)",
                    (tid, uid),
                )
                if method == "sharePhone":
                    share = v.boolean(p.get("share"), "Phone sharing")
                    if share and not r.actor(c, uid)["phone"]:
                        raise AppError("Add a phone number in your profile first.")
                    c.execute(
                        "UPDATE consentbase SET phone_shared=? WHERE thread_id=? AND user_id=?",
                        (int(share), tid, uid),
                    )
                else:
                    if (
                        method == "cancelIdentityReveal"
                        and r.connection(c, uid, tid)["reveal"] == "revealed"
                    ):
                        raise AppError(
                            "Identity has already been shared. End the conversation to stop interacting."
                        )
                    c.execute(
                        "UPDATE consentbase SET identity_reveal=? WHERE thread_id=? AND user_id=?",
                        (int(method == "requestIdentityReveal"), tid, uid),
                    )
            elif method in ("endConversation", "reportConnection", "blockConnection"):
                if method == "reportConnection":
                    reason = v.text(p.get("reason"), "Report reason", 500)
                    c.execute(
                        "INSERT INTO reportbase(thread_id,reporter_id,reported_id,reason) VALUES(?,?,?,?)",
                        (tid, uid, peer, reason),
                    )
                if method != "endConversation":
                    c.execute(
                        "INSERT OR IGNORE INTO blockbase(user_id,other_id) VALUES(?,?)",
                        (uid, peer),
                    )
                c.execute(
                    "UPDATE directthreadbase SET status='ended' WHERE thread_id=?",
                    (tid,),
                )
                return None
            return r.connection(c, uid, tid)

    @staticmethod
    def active(c, table, key, record_id):
        row = r.one(c, f"SELECT status FROM {table} WHERE {key}=?", (record_id,))
        if row["status"] != "published":
            raise AppError(
                "This activity is closed. Choose another active activity.", 409
            )

    @staticmethod
    def message(c, table, key, tid, uid, p):
        value = v.text(p.get("text"), "Message", 1000)
        request = v.text(p.get("requestId"), "Request ID", 128, filtered=False)
        existing = c.execute(
            f"SELECT content FROM {table} WHERE thread_id=? AND sender_id=? AND request_id=?",
            (tid, uid, request),
        ).fetchone()
        if existing:
            if existing[0] != value:
                raise AppError(
                    "This request ID was already used for a different message.", 409
                )
            return
        c.execute(
            f"INSERT INTO {table}(thread_id,sender_id,content,request_id) VALUES(?,?,?,?)",
            (tid, uid, value, request),
        )

    def connect(self, c, uid, p):
        kind = p.get("kind")
        if kind in ("match", "similar-answer", "poll"):
            return self.matching.connect(c, uid, p)
        if kind not in ("daily-answer", "question-response"):
            raise AppError("Choose an available connection source.", 400)
        qid = v.identifier(p.get("questionId"))
        response = v.identifier(p.get("responseId"))
        if kind == "daily-answer":
            r.one(
                c,
                "SELECT 1 FROM dailyquestionbase WHERE thread_id=? AND status IN('published','closed')",
                (qid,),
            )
            row = r.one(
                c,
                "SELECT sender_id,content FROM dailyresponsebase WHERE thread_id=? AND response_id=?",
                (qid, response),
            )
            source = "Daily question"
        elif kind == "question-response":
            row = r.one(
                c,
                "SELECT sender_id,content FROM boardreplybase WHERE post_id=? AND response_id=?",
                (qid, response),
            )
            source = "Question board"
        peer = row["sender_id"]
        if peer == uid:
            raise AppError("Choose someone else's response.")
        if r.blocked(c, uid, peer):
            raise AppError("This connection is unavailable.", 403)
        a, b = sorted((uid, peer))
        existing = c.execute(
            "SELECT thread_id FROM directthreadbase WHERE sender_id=? AND receiver_id=? AND status='open'",
            (a, b),
        ).fetchone()
        tid = (
            existing[0]
            if existing
            else c.execute(
                "INSERT INTO directthreadbase(sender_id,receiver_id,source,shared) VALUES(?,?,?,?)",
                (a, b, source, row["content"]),
            ).lastrowid
        )
        completed = bool(
            c.execute(
                "SELECT 1 FROM directmessagebase WHERE sender_id=? LIMIT 1", (uid,)
            ).fetchone()
        )
        return {"connection": r.connection(c, uid, tid), "completed": completed}

    def messages(self, uid, tid, before):
        uid = v.identifier(uid)
        tid = v.identifier(tid)
        before = v.identifier(before)
        with self.database.transaction() as c:
            r.conversation(c, uid, tid)
            records = list(
                c.execute(
                    "SELECT * FROM directmessagebase WHERE thread_id=? AND msg_id<? ORDER BY msg_id DESC LIMIT ?",
                    (tid, before, r.PAGE_SIZE),
                )
            )
            return [
                {
                    "id": str(m["msg_id"]),
                    "from": "me" if m["sender_id"] == uid else "them",
                    "text": m["content"],
                    "time": m["created_at"],
                }
                for m in reversed(records)
            ]

    def admin_load(self, uid):
        uid = v.identifier(uid)
        with self.database.transaction() as c:
            r.actor(c, uid, admin=True)
            return {
                "dailyQuestions": [
                    r.daily(c, uid, row[0])
                    for row in c.execute(
                        "SELECT thread_id FROM dailyquestionbase ORDER BY thread_id DESC"
                    )
                ],
                "polls": [
                    r.poll(c, uid, row[0], admin=True)
                    for row in c.execute(
                        "SELECT poll_id FROM pollbase ORDER BY poll_id DESC"
                    )
                ],
                "groups": [
                    r.group(c, uid, row[0], admin=True)
                    for row in c.execute(
                        "SELECT thread_id FROM threadbase ORDER BY thread_id DESC"
                    )
                ],
                "reports": [
                    {
                        "id": str(row["report_id"]),
                        "connectionId": str(row["thread_id"]),
                        "reporter": row["reporter"],
                        "reported": row["reported"],
                        "reason": row["reason"],
                        "status": row["status"],
                        "time": row["created_at"],
                        "messages": [
                            {
                                "alias": m["alias"],
                                "text": m["content"],
                                "time": m["created_at"],
                            }
                            for m in c.execute(
                                "SELECT m.content,m.created_at,u.alias FROM directmessagebase m JOIN userbase u ON u.user_id=m.sender_id WHERE m.thread_id=? ORDER BY m.msg_id DESC LIMIT ?",
                                (row["thread_id"], r.PAGE_SIZE),
                            )
                        ],
                    }
                    for row in c.execute(
                        "SELECT r.*,a.alias reporter,b.alias reported FROM reportbase r JOIN userbase a ON a.user_id=r.reporter_id JOIN userbase b ON b.user_id=r.reported_id ORDER BY report_id DESC"
                    )
                ],
            }

    def admin_action(self, uid, method, p):
        if not isinstance(p, dict):
            raise AppError("Invalid request.")
        uid = v.identifier(uid)
        with self.database.transaction(write=True) as c:
            r.actor(c, uid, admin=True)
            if method in ("saveQuestion", "savePoll"):
                is_poll = method == "savePoll"
                table, key = (
                    ("pollbase", "poll_id")
                    if is_poll
                    else ("dailyquestionbase", "thread_id")
                )
                prompt = v.text(p.get("text"), "Question", 500)
                status = p.get("status", "draft")
                if status not in ("draft", "published", "closed", "archived"):
                    raise AppError("Choose a valid activity status.")
                record_id = v.identifier(p["id"]) if p.get("id") else None
                if record_id:
                    r.one(c, f"SELECT 1 FROM {table} WHERE {key}=?", (record_id,))
                    c.execute(
                        f"UPDATE {table} SET prompt=?,status=? WHERE {key}=?",
                        (prompt, status, record_id),
                    )
                else:
                    record_id = c.execute(
                        f"INSERT INTO {table}(prompt,status,creator_id) VALUES(?,?,?)",
                        (prompt, status, uid),
                    ).lastrowid
                if is_poll:
                    public = v.boolean(
                        p.get("resultsPublic", True), "Results visibility"
                    )
                    choices = p.get("choices")
                    if not isinstance(choices, list) or not 2 <= len(choices) <= 8:
                        raise AppError("A poll needs 2–8 choices.")
                    choices = [v.text(choice, "Poll choice", 120) for choice in choices]
                    if len(set(choices)) != len(choices):
                        raise AppError("Poll choices must be different.")
                    current = [
                        row[0]
                        for row in c.execute(
                            "SELECT text FROM pollchoicebase WHERE poll_id=? ORDER BY position",
                            (record_id,),
                        )
                    ]
                    if current != choices:
                        if c.execute(
                            "SELECT 1 FROM pollresponsebase WHERE poll_id=? LIMIT 1",
                            (record_id,),
                        ).fetchone():
                            raise AppError(
                                "This poll has votes. Retain its choices or create a new poll.",
                                409,
                            )
                        c.execute(
                            "DELETE FROM pollchoicebase WHERE poll_id=?", (record_id,)
                        )
                        c.executemany(
                            "INSERT INTO pollchoicebase(poll_id,text,position) VALUES(?,?,?)",
                            [
                                (record_id, choice, i)
                                for i, choice in enumerate(choices)
                            ],
                        )
                    c.execute(
                        "UPDATE pollbase SET results_public=? WHERE poll_id=?",
                        (int(public), record_id),
                    )
            elif method in ("saveGroup", "reviewGroup"):
                record_id = v.identifier(p["id"]) if p.get("id") else None
                if method == "reviewGroup":
                    r.one(
                        c,
                        "SELECT 1 FROM threadbase WHERE thread_id=? AND approval='pending'",
                        (record_id,),
                        "This proposal is no longer pending.",
                    )
                    decision = p.get("decision")
                    if decision not in ("approved", "rejected"):
                        raise AppError("Choose approve or reject.")
                    reason = v.text(p.get("reason", ""), "Decision reason", 500, False)
                    c.execute(
                        "UPDATE threadbase SET approval=?,reviewer_id=?,decided_at=CURRENT_TIMESTAMP,decision_reason=? WHERE thread_id=?",
                        (decision, uid, reason, record_id),
                    )
                else:
                    title = v.text(p.get("name"), "Group name", 100)
                    body = v.text(
                        p.get("description", ""), "Group description", 800, False
                    )
                    status = p.get("status", "open")
                    if status not in ("open", "closed", "archived"):
                        raise AppError("Choose a valid group status.")
                    if record_id:
                        r.one(
                            c,
                            "SELECT 1 FROM threadbase WHERE thread_id=?",
                            (record_id,),
                        )
                        c.execute(
                            "UPDATE threadbase SET title=?,body=?,status=?,approval='approved',reviewer_id=?,decided_at=CURRENT_TIMESTAMP WHERE thread_id=?",
                            (title, body, status, uid, record_id),
                        )
                    else:
                        record_id = c.execute(
                            "INSERT INTO threadbase(title,body,status,approval,creator_id,reviewer_id,decided_at) VALUES(?,?,?,'approved',?,?,CURRENT_TIMESTAMP)",
                            (title, body, status, uid, uid),
                        ).lastrowid
            elif method == "reviewReport":
                record_id = v.identifier(p.get("id"))
                r.one(c, "SELECT 1 FROM reportbase WHERE report_id=?", (record_id,))
                c.execute(
                    "UPDATE reportbase SET status='reviewed' WHERE report_id=?",
                    (record_id,),
                )
            else:
                raise AppError("Unknown administrator action.", 404)
            c.execute(
                "INSERT INTO auditbase(actor_id,action,record_id) VALUES(?,?,?)",
                (uid, method, str(record_id)),
            )
        return self.admin_load(uid)
