# Nota: No agregar tools= a agentes con proveedores de historial — causa errores de ítems duplicados
# con la Responses API. Ver https://github.com/microsoft/agent-framework/issues/3295
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

# Configurar logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configurar cliente de OpenAI según el entorno
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
    """Un proveedor de historial personalizado respaldado por SQLite.

    Implementa HistoryProvider para persistir mensajes de chat
    en una base SQLite local: es útil cuando quieres persistencia
    basada en archivos sin un servicio externo como Redis.
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
        """Recupera todos los mensajes de esta sesión desde SQLite."""
        if session_id is None:
            return []
        cursor = self._conn.execute(
            "SELECT message_json FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [Message.from_json(row[0]) for row in cursor.fetchall()]

    async def save_messages(self, session_id: str | None, messages: Sequence[Message], **kwargs: Any) -> None:
        """Guarda mensajes en la base de datos SQLite."""
        if session_id is None:
            return
        self._conn.executemany(
            "INSERT INTO messages (session_id, message_json) VALUES (?, ?)",
            [(session_id, message.to_json()) for message in messages],
        )
        self._conn.commit()

    def close(self) -> None:
        """Cierra la conexión a SQLite."""
        self._conn.close()


async def main() -> None:
    """Demuestra una sesión con SQLite que persiste el historial en un archivo local."""
    db_path = "chat_history.sqlite3"
    session_id = str(uuid.uuid4())

    # Fase 1: Iniciar una conversación con un proveedor de historial en SQLite
    print("\n[bold]=== Sesión persistente en SQLite ===[/bold]")
    print("[bold]--- Fase 1: Iniciando conversación ---[/bold]")

    sqlite_provider = SQLiteHistoryProvider(db_path=db_path)

    agent = Agent(
        client=client,
        instructions="Eres un asistente útil que recuerda nuestra conversación.",
        context_providers=[sqlite_provider],
    )

    session = agent.create_session(session_id=session_id)

    print("[blue]Usuario:[/blue] ¡Hola! Me llamo Alicia y me encanta el senderismo.")
    response = await agent.run("¡Hola! Me llamo Alicia y me encanta el senderismo.", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    print("\n[blue]Usuario:[/blue] ¿Qué senderos buenos hay en Colorado?")
    response = await agent.run("¿Qué senderos buenos hay en Colorado?", session=session)
    print(f"[green]Agente:[/green] {response.text}")

    # Fase 2: Simular un reinicio de la app — reconectar al mismo session_id en SQLite
    print("\n[bold]--- Fase 2: Reanudando después del 'reinicio' ---[/bold]")
    sqlite_provider2 = SQLiteHistoryProvider(db_path=db_path)

    agent2 = Agent(
        client=client,
        instructions="Eres un asistente útil que recuerda nuestra conversación.",
        context_providers=[sqlite_provider2],
    )

    session2 = agent2.create_session(session_id=session_id)

    print("[blue]Usuario:[/blue] ¿Qué recuerdas de mí?")
    response = await agent2.run("¿Qué recuerdas de mí?", session=session2)
    print(f"[green]Agente:[/green] {response.text}")

    sqlite_provider2.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
