"""JSON view models shared with assets/services/contracts.mjs, not SQL tables.

Keys retain the browser's spelling. These annotations do not validate requests;
the eventual backend must validate inputs and authorize access before using them.
"""

from typing import Literal, TypedDict

Color = Literal["blue", "yellow", "green"]


class Profile(TypedDict):
    id: str
    alias: str
    name: str


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


class PollChoice(TypedDict):
    id: str
    text: str
    icon: str
    percent: float


class Poll(TypedDict):
    id: str
    question: str
    choices: list[PollChoice]
    vote: str | None
    totalVotes: int


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


class AppData(TypedDict):
    profile: Profile
    daily: DailyQuestion
    poll: Poll
    completed: bool
    connections: list[Connection]
    groups: list[Group]
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


ConnectionContext = (
    DailyConnectionContext
    | SimilarConnectionContext
    | PollConnectionContext
    | QuestionConnectionContext
)


class ConnectionResult(TypedDict):
    connection: Connection
    completed: bool
