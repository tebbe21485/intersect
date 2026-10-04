"""Typed asynchronous facade over the implemented transactional application service."""

from dataclasses import dataclass
from typing import Protocol

from .contracts import (
    AppData,
    Connection,
    ConnectionContext,
    ConnectionResult,
    DailyQuestion,
    Group,
    Poll,
    Question,
)


@dataclass(frozen=True)
class RequestContext:
    """Construct on the server from its authenticated session, never client JSON."""

    actor_id: str


class FrontendService(Protocol):
    """Authorize each operation and return committed, viewer-specific records.

    Matching, aliases, message authors, IDs and consent are backend-owned.
    Synchronous SQLite work should run in a worker thread with its own connection.
    No production method exists for simulating another person's consent.
    """

    async def load(self, context: RequestContext) -> AppData: ...

    async def save_daily_answer(
        self,
        context: RequestContext,
        *,
        question_id: str,
        text: str,
    ) -> DailyQuestion: ...

    async def vote_on_poll(
        self,
        context: RequestContext,
        *,
        poll_id: str,
        choice_id: str,
    ) -> Poll: ...

    async def create_connection(
        self,
        context: RequestContext,
        *,
        source: ConnectionContext,
    ) -> ConnectionResult: ...

    async def send_message(
        self,
        context: RequestContext,
        *,
        connection_id: str,
        text: str,
        request_id: str,
    ) -> Connection: ...

    async def join_group(
        self,
        context: RequestContext,
        *,
        group_id: str,
    ) -> Group: ...

    async def send_group_message(
        self,
        context: RequestContext,
        *,
        group_id: str,
        text: str,
        request_id: str,
    ) -> Group: ...

    async def post_question(
        self,
        context: RequestContext,
        *,
        category: str,
        text: str,
        detail: str,
    ) -> Question: ...

    async def reply_to_question(
        self,
        context: RequestContext,
        *,
        question_id: str,
        text: str,
    ) -> Question: ...

    async def request_identity_reveal(
        self,
        context: RequestContext,
        *,
        connection_id: str,
    ) -> Connection: ...

    async def cancel_identity_reveal(
        self,
        context: RequestContext,
        *,
        connection_id: str,
    ) -> Connection: ...

    async def end_conversation(
        self,
        context: RequestContext,
        *,
        connection_id: str,
    ) -> None: ...

    async def report_connection(
        self,
        context: RequestContext,
        *,
        connection_id: str,
        reason: str,
    ) -> None:
        """Report and block atomically; the current UI removes the conversation."""
        ...

    async def block_connection(
        self,
        context: RequestContext,
        *,
        connection_id: str,
    ) -> None: ...


class SQLiteFrontendService:
    """Async integration facade; every transaction stays in its worker thread."""

    def __init__(self, database, embedding_generator=None):
        from .application import ApplicationService

        self.application = ApplicationService(database, embedding_generator)

    async def load(self, context: RequestContext, *, after_messages=None) -> AppData:
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(
            self.application.load, context.actor_id, after_messages
        )

    async def dispatch(self, context: RequestContext, method: str, payload: dict):
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(
            self.application.action, context.actor_id, method, payload
        )

    async def save_daily_answer(self, context, *, question_id, text):
        return await self.dispatch(
            context, "saveDailyAnswer", {"questionId": question_id, "text": text}
        )

    async def vote_on_poll(self, context, *, poll_id, choice_id):
        return await self.dispatch(
            context, "voteOnPoll", {"pollId": poll_id, "choiceId": choice_id}
        )

    async def create_connection(self, context, *, source):
        return await self.dispatch(context, "createConnection", source)

    async def send_message(self, context, *, connection_id, text, request_id):
        return await self.dispatch(
            context,
            "sendMessage",
            {"connectionId": connection_id, "text": text, "requestId": request_id},
        )

    async def join_group(self, context, *, group_id):
        return await self.dispatch(context, "joinGroup", {"groupId": group_id})

    async def send_group_message(self, context, *, group_id, text, request_id):
        return await self.dispatch(
            context,
            "sendGroupMessage",
            {"groupId": group_id, "text": text, "requestId": request_id},
        )

    async def post_question(self, context, *, category, text, detail):
        return await self.dispatch(
            context,
            "postQuestion",
            {"category": category, "text": text, "detail": detail},
        )

    async def reply_to_question(self, context, *, question_id, text):
        return await self.dispatch(
            context, "replyToQuestion", {"questionId": question_id, "text": text}
        )

    async def request_identity_reveal(self, context, *, connection_id):
        return await self.dispatch(
            context, "requestIdentityReveal", {"connectionId": connection_id}
        )

    async def cancel_identity_reveal(self, context, *, connection_id):
        return await self.dispatch(
            context, "cancelIdentityReveal", {"connectionId": connection_id}
        )

    async def end_conversation(self, context, *, connection_id):
        return await self.dispatch(
            context, "endConversation", {"connectionId": connection_id}
        )

    async def report_connection(self, context, *, connection_id, reason):
        return await self.dispatch(
            context,
            "reportConnection",
            {"connectionId": connection_id, "reason": reason},
        )

    async def block_connection(self, context, *, connection_id):
        return await self.dispatch(
            context, "blockConnection", {"connectionId": connection_id}
        )
