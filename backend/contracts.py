"""JSON view models shared with assets/services/contracts.mjs, not SQL tables.

Keys retain the browser's spelling. API inputs are validated by validation.py;
application.py authorizes and returns these viewer-specific projections.
"""

from typing import Literal, NotRequired, TypedDict

Color = Literal["blue", "yellow", "green"]


class Profile(TypedDict):
    id: str
    alias: str
    name: str
    firstName: str
    lastName: str
    linkedin: str
    phone: str
    email: str | None
    role: Literal["user", "admin"]


class DailyResponse(TypedDict):
    id: str
    alias: str
    color: Color
    text: str
    interest: str


class DailyQuestion(TypedDict):
    id: str
    text: str
    answer: str
    responses: list[DailyResponse]
    status: Literal["draft", "published", "closed", "archived"]


class PollChoice(TypedDict):
    id: str
    text: str
    icon: str
    percent: float | None


class Poll(TypedDict):
    id: str
    question: str
    choices: list[PollChoice]
    vote: str | None
    totalVotes: int | None
    resultsPublic: bool
    status: Literal["draft", "published", "closed", "archived"]


Message = TypedDict(
    "Message",
    {
        "id": str,
        "from": Literal["me", "them"],
        "text": str,
        "time": str,
    },
)


class Connection(TypedDict):
    id: str
    alias: str
    color: Color
    source: str
    shared: str
    interests: list[str]
    preview: str
    time: str
    messages: list[Message]
    reveal: Literal["waiting", "revealed"] | None
    identity: str | None  # Must be None until both people consent.
    identityDetails: "PeerIdentity | None"
    myConsent: bool
    peerConsent: bool
    phone: str | None  # Only after the owner separately shares with this recipient.
    phoneShared: bool
    hasOlderMessages: bool
    incremental: bool


class PeerIdentity(TypedDict):
    firstName: str
    lastName: str
    linkedin: str


class Response(TypedDict):
    id: str
    alias: str
    text: str
    isMine: bool


class Question(TypedDict):
    id: str
    category: str
    text: str
    detail: str
    alias: str
    time: str
    responses: list[Response]


class GroupMessage(Message):
    alias: str


class Group(TypedDict):
    id: str
    name: str
    icon: str
    color: Color
    size: int
    description: str
    activity: str
    question: str
    joined: bool
    messages: list[GroupMessage]
    approval: Literal["pending", "approved", "rejected"]
    status: Literal["open", "closed", "archived"]
    decisionReason: str
    isMine: bool


class AppData(TypedDict):
    profile: Profile
    dailyQuestions: list[DailyQuestion]
    polls: list[Poll]
    completed: bool
    connections: list[Connection]
    groups: list[Group]
    groupProposals: list[Group]
    questions: list[Question]
    categories: list[str]


class DailyConnectionContext(TypedDict):
    kind: Literal["daily-answer"]
    questionId: str
    responseId: str


class SimilarConnectionContext(TypedDict):
    kind: Literal["similar-answer"]
    questionId: str


class PollConnectionContext(TypedDict):
    kind: Literal["poll"]
    pollId: str


class QuestionConnectionContext(TypedDict):
    kind: Literal["question-response"]
    questionId: str
    responseId: str


class MatchingTrait(TypedDict):
    category: Literal["puzzle", "daily_questions", "polls", "groups", "personal"]
    value: str | int
    field: NotRequired[str]


class MatchConnectionContext(TypedDict):
    kind: Literal["match"]
    mode: NotRequired[Literal["similar", "different", "trait"]]
    userId: NotRequired[str | int]
    trait: NotRequired[MatchingTrait]


class MatchingCandidate(TypedDict):
    user_id: int
    alias: str
    overall_similarity: float
    category_scores: dict[str, float | None]
    effective_weights: dict[str, float]
    effective_subweights: dict[str, float]
    connection_mode: Literal["similar", "different", "trait"]
    shared_anchors: list[str]
    match_reason: str
    puzzle_details: dict
    comparable_counts: dict[str, int]
    algorithm: str
    trait_similarity: NotRequired[float]


ConnectionContext = (
    DailyConnectionContext
    | SimilarConnectionContext
    | PollConnectionContext
    | QuestionConnectionContext
    | MatchConnectionContext
)


class ConnectionResult(TypedDict):
    connection: Connection
    completed: bool
    match: NotRequired[MatchingCandidate]
