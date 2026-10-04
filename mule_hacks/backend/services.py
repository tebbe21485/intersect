"""Contract for a future Reflex-hosted backend. No implementation is connected."""

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
