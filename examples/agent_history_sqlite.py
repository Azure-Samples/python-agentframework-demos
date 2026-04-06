# Note: Do not add tools= to agents using history providers — causes duplicate item errors
# with the Responses API. See https://github.com/microsoft/agent-framework/issues/3295
import asyncio
import logging
import os
import sqlite3
import uuid
from collections.abc import Sequence
from typing import Any

from agent_framework import Agent, HistoryProvider, Message
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich import print
from rich.logging import RichHandler

# Setup logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure OpenAI client based on environment
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )


class SQLiteHistoryProvider(HistoryProvider):
    """A custom history provider backed by SQLite.

    Implements the HistoryProvider to persist chat messages
    in a local SQLite database — useful when you want file-based
    persistence without an external service like Redis.
    """

    def __init__(self, db_path: str):
        super().__init__("sqlite-history")
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    async def get_messages(self, session_id: str | None, **kwargs: Any) -> list[Message]:
        """Retrieve all messages for this session from SQLite."""
        if session_id is None:
            return []
        cursor = self._conn.execute(
            "SELECT message_json FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [Message.from_json(row[0]) for row in cursor.fetchall()]

    async def save_messages(self, session_id: str | None, messages: Sequence[Message], **kwargs: Any) -> None:
        """Save messages to the SQLite database."""
        if session_id is None:
            return
        self._conn.executemany(
            "INSERT INTO messages (session_id, message_json) VALUES (?, ?)",
            [(session_id, message.to_json()) for message in messages],
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()


async def main() -> None:
    """Demonstrate a SQLite-backed session that persists conversation history to a local file."""
    db_path = "chat_history.sqlite3"
    session_id = str(uuid.uuid4())

    # Phase 1: Start a conversation with a SQLite-backed history provider
    print("\n[bold]=== Persistent SQLite Session ===[/bold]")
    print("[bold]--- Phase 1: Starting conversation ---[/bold]")

    sqlite_provider = SQLiteHistoryProvider(db_path=db_path)

    agent = Agent(
        client=client,
        instructions="You are a helpful assistant that remembers our conversation.",
        context_providers=[sqlite_provider],
    )

    session = agent.create_session(session_id=session_id)

    print("[blue]User:[/blue] Hello! My name is Alice and I love hiking.")
    response = await agent.run("Hello! My name is Alice and I love hiking.", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    print("\n[blue]User:[/blue] What are some good trails in Colorado?")
    response = await agent.run("What are some good trails in Colorado?", session=session)
    print(f"[green]Agent:[/green] {response.text}")

    # Phase 2: Simulate an application restart — reconnect to the same session ID in SQLite
    print("\n[bold]--- Phase 2: Resuming after 'restart' ---[/bold]")
    sqlite_provider2 = SQLiteHistoryProvider(db_path=db_path)

    agent2 = Agent(
        client=client,
        instructions="You are a helpful assistant that remembers our conversation.",
        context_providers=[sqlite_provider2],
    )

    session2 = agent2.create_session(session_id=session_id)

    print("[blue]User:[/blue] What do you remember about me?")
    response = await agent2.run("What do you remember about me?", session=session2)
    print(f"[green]Agent:[/green] {response.text}")

    sqlite_provider2.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
