"""
Recuperación de conocimiento (RAG) mediante un proveedor de contexto personalizado.

Diagrama:

 Entrada ──▶ Agente ──────────────────▶ LLM ──▶ Respuesta
               │                        ▲
               │  buscar con entrada    │ conocimiento relevante
               ▼                        │
         ┌────────────┐                 │
         │   Base de   │────────────────┘
         │ conocimiento│
         │  (SQLite)   │
         └────────────┘

El agente recupera conocimiento de una base de datos SQLite FTS5 *antes*
de pedirle al LLM que responda. Como el agente siempre necesita conocimiento
específico del dominio para fundamentar sus respuestas, un paso de búsqueda
determinista es más eficiente y confiable que pedirle al LLM que decida
usar una herramienta.

Este ejemplo crea un pequeño catálogo de productos y usa un
ContextProvider personalizado para inyectar filas relevantes en el contexto del LLM.
"""

import asyncio
import logging
import os
import re
import sqlite3
import sys
from typing import Any

from agent_framework import Agent, AgentSession, ContextProvider, Message, SessionContext, SupportsAgentRun
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich import print
from rich.logging import RichHandler

# ── Logging ──────────────────────────────────────────────────────────
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Cliente OpenAI ───────────────────────────────────────────────────
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


# ── Base de conocimiento (SQLite + FTS5) ─────────────────────────────

PRODUCTS = [
    {
        "name": "Botas de Senderismo TrailBlaze",
        "category": "Calzado",
        "price": 149.99,
        "description": (
            "Botas de senderismo impermeables con suelas Vibram, soporte de tobillo "
            "y forro transpirable Gore-Tex. Ideales para senderos rocosos y condiciones húmedas."
        ),
    },
    {
        "name": "Mochila SummitPack 40L",
        "category": "Mochilas",
        "price": 89.95,
        "description": (
            "Mochila ligera de 40 litros con compartimento para hidratación, cubierta de lluvia "
            "y cinturón de cadera ergonómico. Perfecta para excursiones de un día o con pernocta."
        ),
    },
    {
        "name": "Chaqueta de Plumón ArcticShield",
        "category": "Ropa",
        "price": 199.00,
        "description": (
            "Chaqueta de plumón de ganso 800-fill con clasificación de -28°C. "
            "Incluye carcasa resistente al agua, diseño comprimible y capucha ajustable."
        ),
    },
    {
        "name": "Remo para Kayak RiverRun",
        "category": "Deportes Acuáticos",
        "price": 74.50,
        "description": (
            "Remo de fibra de vidrio para kayak con férula ajustable y anillos antigoteo. "
            "Ligero (795 g), apto para kayak recreativo y de travesía."
        ),
    },
    {
        "name": "Bastones de Trekking TerraFirm",
        "category": "Accesorios",
        "price": 59.99,
        "description": (
            "Bastones de trekking plegables de fibra de carbono con empuñaduras de corcho y puntas de tungsteno. "
            "Ajustables de 60 a 137 cm, con amortiguación anti-vibración."
        ),
    },
    {
        "name": "Binoculares ClearView 10x42",
        "category": "Óptica",
        "price": 129.00,
        "description": (
            "Binoculares de prisma de techo con aumento 10x y lentes objetivos de 42 mm. "
            "Cargados con nitrógeno y resistentes al agua. Ideales para observación de aves y fauna."
        ),
    },
    {
        "name": "Linterna Frontal LED NightGlow",
        "category": "Iluminación",
        "price": 34.99,
        "description": (
            "Linterna frontal recargable de 350 lúmenes con modo de luz roja y haz ajustable. "
            "Clasificación IPX6 de resistencia al agua, hasta 40 horas en modo bajo."
        ),
    },
    {
        "name": "Saco de Dormir CozyNest",
        "category": "Camping",
        "price": 109.00,
        "description": (
            "Saco de dormir tipo momia para tres estaciones, con clasificación de -6°C. "
            "Aislamiento sintético, saco de compresión incluido. Pesa 1.1 kg."
        ),
    },
]


def create_knowledge_db(db_path: str) -> sqlite3.Connection:
    """Crea (o recrea) el catálogo de productos en SQLite con un índice FTS5."""
    conn = sqlite3.connect(db_path)

    # Eliminar tablas existentes para empezar de nuevo
    conn.execute("DROP TABLE IF EXISTS products_fts")
    conn.execute("DROP TABLE IF EXISTS products")

    conn.execute(
        """
        CREATE TABLE products (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO products (name, category, price, description) VALUES (?, ?, ?, ?)",
        [(p["name"], p["category"], p["price"], p["description"]) for p in PRODUCTS],
    )

    # Crear índice de búsqueda de texto completo sobre nombre, categoría y descripción
    conn.execute(
        """
        CREATE VIRTUAL TABLE products_fts USING fts5(
            name, category, description,
            content='products',
            content_rowid='id'
        )
        """
    )
    conn.execute(
        "INSERT INTO products_fts (rowid, name, category, description) "
        "SELECT id, name, category, description FROM products"
    )
    conn.commit()
    return conn


# ── Proveedor de contexto personalizado para recuperación de conocimiento ──


class SQLiteKnowledgeProvider(ContextProvider):
    """Recupera conocimiento relevante de productos desde SQLite FTS5 antes de cada llamada al LLM.

    Sigue el patrón de "recuperación de conocimiento" donde el agente busca
    de manera determinista en una base de conocimiento *antes* de que el LLM
    se ejecute, en lugar de depender de que el LLM decida llamar a una herramienta
    de búsqueda. Esto asegura que el modelo siempre tenga contexto específico
    del dominio para fundamentar su respuesta.
    """

    def __init__(self, db_conn: sqlite3.Connection, max_results: int = 3):
        super().__init__(source_id="sqlite-knowledge")
        self.db_conn = db_conn
        self.max_results = max_results

    def _search(self, query: str) -> list[dict]:
        """Ejecuta una consulta FTS5 y devuelve productos coincidentes."""
        # Extraer palabras, filtrar cortas (len <= 2 elimina "a", "de", "el", etc.)
        words = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]+", query)
        tokens = [w.lower() for w in words if len(w) > 2]
        if not tokens:
            return []
        fts_query = " OR ".join(tokens)

        try:
            cursor = self.db_conn.execute(
                """
                SELECT p.name, p.category, p.price, p.description
                FROM products_fts fts
                JOIN products p ON fts.rowid = p.id
                WHERE products_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, self.max_results),
            )
            return [
                {"name": row[0], "category": row[1], "price": row[2], "description": row[3]}
                for row in cursor.fetchall()
            ]
        except Exception:
            logger.debug("Consulta FTS falló para: %s", fts_query, exc_info=True)
            return []

    def _format_results(self, results: list[dict]) -> str:
        """Formatea los resultados de búsqueda como texto para el contexto del LLM."""
        lines = ["Información relevante de productos de nuestro catálogo:\n"]
        for product in results:
            lines.append(
                f"- **{product['name']}** ({product['category']}, ${product['price']:.2f}): "
                f"{product['description']}"
            )
        return "\n".join(lines)

    async def before_run(
        self,
        *,
        agent: SupportsAgentRun,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Busca en la base de conocimiento con el último mensaje del usuario e inyecta resultados."""
        user_text = next(
            (msg.text for msg in reversed(context.input_messages) if msg.role == "user" and msg.text), None
        )
        if not user_text:
            return

        results = self._search(user_text)
        if not results:
            logger.info("[📚 Conocimiento] No se encontraron productos para: %s", user_text)
            return

        logger.info("[📚 Conocimiento] Se encontraron %d producto(s) para: %s", len(results), user_text)

        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[self._format_results(results)])],
        )


# ── Configuración del agente ─────────────────────────────────────────

DB_PATH = ":memory:"  # BD en memoria — no necesita limpieza de archivos

# Crear y poblar la base de conocimiento
db_conn = create_knowledge_db(DB_PATH)
knowledge_provider = SQLiteKnowledgeProvider(db_conn=db_conn)

agent = Agent(
    client=client,
    instructions=(
        "Eres un asistente de compras de equipo para actividades al aire libre de la tienda 'TrailBuddy'. "
        "Responde las preguntas del cliente usando SOLO la información de productos proporcionada en el contexto. "
        "Si no se encuentran productos relevantes en el contexto, di que no tienes información sobre ese artículo. "
        "Incluye precios al recomendar productos."
    ),
    context_providers=[knowledge_provider],
)


async def main() -> None:
    """Demuestra el patrón de recuperación de conocimiento (RAG) con varias consultas."""
    # Consulta 1: Debería encontrar botas de senderismo y bastones de trekking
    print("\n[bold]=== Demo de Recuperación de Conocimiento (RAG) ===[/bold]")
    print("[blue]Usuario:[/blue] Estoy planeando una excursión. ¿Qué botas y bastones me recomiendan?")
    response = await agent.run("Estoy planeando una excursión. ¿Qué botas y bastones me recomiendan?")
    print(f"[green]Agente:[/green] {response.text}\n")

    # Consulta 2: Sin coincidencia — demuestra manejo de "sin conocimiento"
    print("[blue]Usuario:[/blue] ¿Tienen tablas de surf?")
    response = await agent.run("¿Tienen tablas de surf?")
    print(f"[green]Agente:[/green] {response.text}\n")

    db_conn.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())
