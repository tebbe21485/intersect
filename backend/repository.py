"""Focused SQL reads and viewer-specific projections; never expose raw user rows."""

from .auth import profile
from .errors import AppError
from .validation import identifier

CATEGORIES = (
    "Getting to know you",
    "Work & ideas",
    "Life & interests",
    "Something else",
)
PAGE_SIZE = 100


def one(c, sql, params=(), message="That record is no longer available."):
    row = c.execute(sql, params).fetchone()
    if not row:
        raise AppError(message, 404)
    return row


def actor(c, uid, admin=False):
    row = one(
        c,
        "SELECT * FROM userbase WHERE user_id=?",
        (identifier(uid),),
        "Please sign in.",
    )
    if admin and row["role"] != "admin":
        raise AppError("Administrator access is required.", 403)
    return row


def blocked(c, a, b):
    return bool(
        c.execute(
            "SELECT 1 FROM blockbase WHERE (user_id=? AND other_id=?) OR (user_id=? AND other_id=?)",
            (a, b, b, a),
        ).fetchone()
    )


def conversation(c, uid, tid):
    row = one(
        c,
        "SELECT * FROM directthreadbase WHERE thread_id=? AND ? IN(sender_id,receiver_id)",
        (identifier(tid), uid),
    )
    peer = row["receiver_id"] if row["sender_id"] == uid else row["sender_id"]
    if row["status"] != "open" or blocked(c, uid, peer):
        raise AppError("This conversation is no longer available.", 403)
    return row, peer


def daily(c, uid, qid):
    row = one(
        c, "SELECT * FROM dailyquestionbase WHERE thread_id=?", (identifier(qid),)
    )
    answer = c.execute(
        "SELECT content FROM dailyresponsebase WHERE thread_id=? AND sender_id=?",
        (qid, uid),
    ).fetchone()
    responses = [
        {
            "id": str(r["response_id"]),
            "alias": r["alias"],
            "color": "blue",
            "text": r["content"],
            "interest": "Shared perspective",
        }
        for r in c.execute(
            "SELECT r.*,u.alias FROM dailyresponsebase r JOIN userbase u ON u.user_id=r.sender_id WHERE r.thread_id=? AND r.sender_id!=? AND NOT EXISTS(SELECT 1 FROM blockbase b WHERE (b.user_id=? AND b.other_id=r.sender_id) OR (b.other_id=? AND b.user_id=r.sender_id)) ORDER BY r.response_id DESC LIMIT ?",
            (qid, uid, uid, uid, PAGE_SIZE),
        )
    ]
    return {
        "id": str(qid),
        "text": row["prompt"],
        "answer": answer[0] if answer else "",
        "status": row["status"],
        "responses": responses,
    }


def poll(c, uid, pid, admin=False):
    row = one(c, "SELECT * FROM pollbase WHERE poll_id=?", (identifier(pid),))
    visible = bool(row["results_public"]) or admin
    counts = {
        r[0]: r[1]
        for r in c.execute(
            "SELECT choice_id,COUNT(*) FROM pollresponsebase WHERE poll_id=? GROUP BY choice_id",
            (pid,),
        )
    }
    total = sum(counts.values())
    choices = []
    for choice in c.execute(
        "SELECT * FROM pollchoicebase WHERE poll_id=? ORDER BY position", (pid,)
    ):
        value = {
            "id": str(choice["choice_id"]),
            "text": choice["text"],
            "icon": "sparkles",
            "percent": round(100 * counts.get(choice["choice_id"], 0) / total, 1)
            if total and visible
            else (0 if visible else None),
        }
        if admin:
            value["count"] = counts.get(choice["choice_id"], 0)
        choices.append(value)
    vote = c.execute(
        "SELECT choice_id FROM pollresponsebase WHERE poll_id=? AND sender_id=?",
        (pid, uid),
    ).fetchone()
    return {
        "id": str(pid),
        "question": row["prompt"],
        "choices": choices,
        "vote": str(vote[0]) if vote else None,
        "totalVotes": total if visible else None,
        "resultsPublic": bool(row["results_public"]),
        "status": row["status"],
    }


def floor_progress(c, tid, participants):
    row = c.execute("SELECT current_floor FROM connectionfloorbase WHERE thread_id=?", (tid,)).fetchone()
    floor = row[0] if row else 1
    preferences = {row["user_id"]: row for row in c.execute("SELECT * FROM floorparticipantbase WHERE thread_id=?", (tid,))}
    counts = {str(owner): min(2, c.execute("SELECT COUNT(*) FROM directmessagebase WHERE thread_id=? AND sender_id=? AND floor=? AND kind='message'", (tid, owner, floor)).fetchone()[0]) for owner in participants}
    minimum = all(count >= 2 for count in counts.values())
    return {"participantIds": [str(owner) for owner in participants], "currentFloor": floor,
        "counts": counts, "ready": {str(owner): bool(preferences.get(owner) and preferences[owner]["ready"]) for owner in participants},
        "sensitive": {str(owner): bool(preferences.get(owner) and preferences[owner]["sensitive"]) for owner in participants},
        "canAdvance": floor < 4 and minimum, "identityAvailable": floor > 2 or (floor == 2 and minimum),
        "allowSensitivePrompts": all(preferences.get(owner) and preferences[owner]["sensitive"] for owner in participants)}


def puzzle_owners(c, tid, uid, participants):
    owners = []
    shared = {row["piece_id"]: row for row in c.execute("SELECT * FROM sharedpuzzlepiecebase WHERE thread_id=?", (tid,))}
    for owner in sorted(participants):
        alias = one(c, "SELECT alias FROM userbase WHERE user_id=?", (owner,))[0]
        pieces = []
        for piece in c.execute("SELECT * FROM puzzlepiecebase WHERE user_id=? ORDER BY piece_id", (owner,)):
            reveal = shared.get(piece["piece_id"])
            title = reveal["title"] if reveal else piece["title"] or piece["category"].replace("_", " ").title()[:20]
            description = reveal["description"] if reveal else piece["content"]
            pieces.append({"id": str(piece["piece_id"]), "ownerId": str(owner),
                "shortLabel": title if owner == uid or reveal else "", "description": description if owner == uid or reveal else "",
                "isShared": bool(reveal)})
        owners.append({"id": str(owner), "alias": alias, "color": f"hsl({owner * 137 % 360} 50% 35%)", "pieces": pieces})
    return owners


def connection(c, uid, tid, after=None):
    row, peer_id = conversation(c, uid, tid)
    peer = one(c, "SELECT * FROM userbase WHERE user_id=?", (peer_id,))
    consent = {
        r["user_id"]: r
        for r in c.execute("SELECT * FROM consentbase WHERE thread_id=?", (tid,))
    }
    own = consent.get(uid)
    other = consent.get(peer_id)
    mine = bool(own and own["identity_reveal"])
    theirs = bool(other and other["identity_reveal"])
    mutual = mine and theirs
    if after is None:
        records = list(
            reversed(
                list(
                    c.execute(
                        "SELECT * FROM directmessagebase WHERE thread_id=? ORDER BY msg_id DESC LIMIT ?",
                        (tid, PAGE_SIZE),
                    )
                )
            )
        )
    else:
        records = c.execute(
            "SELECT * FROM directmessagebase WHERE thread_id=? AND msg_id>? ORDER BY msg_id LIMIT ?",
            (tid, after, PAGE_SIZE),
        ).fetchall()
    latest = c.execute(
        "SELECT content,created_at FROM directmessagebase WHERE thread_id=? ORDER BY msg_id DESC LIMIT 1",
        (tid,),
    ).fetchone()
    messages = [
        {
            "id": str(m["msg_id"]),
            "from": "me" if m["sender_id"] == uid else "them",
            "text": m["content"],
            "time": m["created_at"],
            "kind": m["kind"],
            "floor": m["floor"],
        }
        for m in records
    ]
    return {
        "id": str(tid),
        "peerId": str(peer_id),
        "puzzleKey": f"connection:{tid}",
        "puzzleOwners": puzzle_owners(c, tid, uid, [uid, peer_id]),
        "floorProgress": {**floor_progress(c, tid, [uid, peer_id]), "messages": [{"text": m["content"]} for m in records if m["kind"] == "message"]},
        "alias": peer["alias"],
        "color": "blue",
        "source": row["source"],
        "shared": row["shared"],
        "interests": [],
        "preview": latest["content"] if latest else "Start a conversation",
        "time": latest["created_at"] if latest else row["created_at"],
        "messages": messages,
        "incremental": after is not None,
        "reveal": "revealed" if mutual else ("waiting" if mine else None),
        "myConsent": mine,
        "peerConsent": theirs,
        "identity": f"{peer['first_name']} {peer['last_name']}".strip()
        if mutual
        else None,
        "identityDetails": {
            "firstName": peer["first_name"],
            "lastName": peer["last_name"],
            "linkedin": peer["linkedin"],
        }
        if mutual
        else None,
        "phone": peer["phone"] if other and other["phone_shared"] else None,
        "phoneShared": bool(own and own["phone_shared"]),
        "hasOlderMessages": c.execute(
            "SELECT COUNT(*) FROM directmessagebase WHERE thread_id=?", (tid,)
        ).fetchone()[0]
        > PAGE_SIZE,
    }


def group(c, uid, gid, admin=False):
    row = one(c, "SELECT * FROM threadbase WHERE thread_id=?", (identifier(gid),))
    public = row["approval"] == "approved" and row["status"] == "open"
    if not public and not admin and row["creator_id"] != uid:
        raise AppError("That group is not available.", 404)
    joined = bool(
        c.execute(
            "SELECT 1 FROM threadmemberbase WHERE thread_id=? AND user_id=?", (gid, uid)
        ).fetchone()
    )
    messages = []
    if public and joined or admin:
        messages = [
            {
                "id": str(m["response_id"]),
                "from": "me" if m["sender_id"] == uid else "them",
                "alias": m["alias"],
                "text": m["content"],
                "time": m["created_at"],
            }
            for m in reversed(
                list(
                    c.execute(
                        "SELECT m.*,u.alias FROM threadmessagebase m JOIN userbase u ON u.user_id=m.sender_id WHERE m.thread_id=? ORDER BY m.response_id DESC LIMIT ?",
                        (gid, PAGE_SIZE),
                    )
                )
            )
        ]
    return {
        "id": str(gid),
        "name": row["title"],
        "description": row["body"],
        "icon": "users",
        "color": "blue",
        "size": c.execute(
            "SELECT COUNT(*) FROM threadmemberbase WHERE thread_id=?", (gid,)
        ).fetchone()[0],
        "activity": "Open discussion" if public else row["approval"],
        "question": row["body"],
        "joined": joined,
        "messages": messages,
        "approval": row["approval"],
        "status": row["status"],
        "decisionReason": row["decision_reason"],
        "isMine": row["creator_id"] == uid,
    }


def board(c, uid, qid):
    row = one(
        c,
        "SELECT p.*,u.alias FROM boardpostbase p JOIN userbase u ON u.user_id=p.sender_id WHERE post_id=?",
        (identifier(qid),),
    )
    responses = [
        {
            "id": str(r["response_id"]),
            "alias": r["alias"],
            "text": r["content"],
            "isMine": r["sender_id"] == uid,
        }
        for r in c.execute(
            "SELECT r.*,u.alias FROM boardreplybase r JOIN userbase u ON u.user_id=r.sender_id WHERE post_id=? ORDER BY response_id DESC LIMIT ?",
            (qid, PAGE_SIZE),
        )
    ]
    return {
        "id": str(qid),
        "category": row["category"],
        "text": row["title"],
        "detail": row["detail"],
        "alias": row["alias"],
        "time": row["created_at"],
        "responses": responses,
    }


def snapshot(c, uid, after_messages=None):
    owner = actor(c, uid)
    connections = []
    for row in c.execute(
        "SELECT thread_id,sender_id,receiver_id FROM directthreadbase WHERE status='open' AND ? IN(sender_id,receiver_id) ORDER BY thread_id DESC",
        (uid,),
    ).fetchall():
        peer = row["receiver_id"] if row["sender_id"] == uid else row["sender_id"]
        if not blocked(c, uid, peer):
            after = (after_messages or {}).get(str(row["thread_id"]))
            connections.append(connection(c, uid, row["thread_id"], after=after))
    return {
        "profile": profile(owner),
        "dailyQuestions": [
            daily(c, uid, r[0])
            for r in c.execute(
                "SELECT thread_id FROM dailyquestionbase WHERE status IN('published','closed') ORDER BY thread_id DESC LIMIT ?",
                (PAGE_SIZE,),
            )
        ],
        "polls": [
            poll(c, uid, r[0])
            for r in c.execute(
                "SELECT poll_id FROM pollbase WHERE status IN('published','closed') ORDER BY poll_id DESC LIMIT ?",
                (PAGE_SIZE,),
            )
        ],
        "connections": connections,
        "completed": bool(
            c.execute(
                "SELECT 1 FROM directmessagebase WHERE sender_id=? LIMIT 1", (uid,)
            ).fetchone()
        ),
        "groups": [
            group(c, uid, r[0])
            for r in c.execute(
                "SELECT thread_id FROM threadbase WHERE approval='approved' AND status='open' ORDER BY thread_id DESC LIMIT ?",
                (PAGE_SIZE,),
            )
        ],
        "groupProposals": [
            group(c, uid, r[0])
            for r in c.execute(
                "SELECT thread_id FROM threadbase WHERE creator_id=? ORDER BY thread_id DESC LIMIT ?",
                (uid, PAGE_SIZE),
            )
        ],
        "questions": [
            board(c, uid, r[0])
            for r in c.execute(
                "SELECT post_id FROM boardpostbase ORDER BY post_id DESC LIMIT ?",
                (PAGE_SIZE,),
            )
        ],
        "categories": list(CATEGORIES),
    }
