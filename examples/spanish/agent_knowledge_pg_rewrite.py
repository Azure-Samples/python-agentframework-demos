"""Recuperación de conocimiento con reescritura de consultas para conversaciones multi-turno.

Diagrama:

 Historial de     ──▶ "Sugiere una      ──▶ LLM ──▶ Consulta     ──▶ Base de
 conversación         consulta basada               reescrita        conocimiento
                                            en esta conversación"

En una conversación multi-turno, el último mensaje del usuario a menudo
carece de contexto importante. Por ejemplo:

    Usuario: "Necesito protección contra la lluvia en senderos rocosos."
    Agente: "¡Checa nuestra chaqueta de plumón y botas de senderismo!"
    Usuario: "¿Qué equipo similar tienen para situaciones con nieve?"

Si buscas solo "¿Qué equipo similar tienen para situaciones con nieve?"
se pierde el contexto de que el usuario está interesado en chaquetas y botas.

Un paso de reescritura le pide al LLM sintetizar toda la conversación
en una sola consulta autocontenida; por ejemplo, "chaquetas y botas
protectores para senderismo en nieve", lo que mejora bastante la recuperación.

Este ejemplo se basa en agent_knowledge_postgres.py y agrega un paso de
reescritura con LLM dentro del método ``before_run`` del proveedor de contexto.

Requisitos:
    - PostgreSQL con extensión pgvector (ver docker-compose.yml)
    - Un modelo de embeddings (Azure OpenAI u OpenAI)
"""

import asyncio
import logging
import os
import sys
from typing import Any

import psycopg
from agent_framework import Agent, AgentSession, ContextProvider, Message, SessionContext, SupportsAgentRun
from agent_framework.openai import OpenAIChatClient
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity import get_bearer_token_provider as sync_get_bearer_token_provider
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from rich import print
from rich.logging import RichHandler

# ── Logging ──────────────────────────────────────────────────────────
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Clientes OpenAI (chat + embeddings) ─────────────────────────────
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://admin:LocalPasswordOnly@db:5432/postgres")
EMBEDDING_DIMENSIONS = 256  # Dimensión reducida para eficiencia

async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    async_token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    sync_credential = SyncDefaultAzureCredential()
    sync_token_provider = sync_get_bearer_token_provider(
        sync_credential, "https://cognitiveservices.azure.com/.default"
    )
    chat_client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=async_token_provider,
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
    embed_client = OpenAI(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=sync_token_provider(),
    )
    embed_model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
else:
    chat_client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )
    embed_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    embed_model = "text-embedding-3-small"


def get_embedding(text: str) -> list[float]:
    """Obtiene un vector de embedding para el texto dado."""
    response = embed_client.embeddings.create(input=text, model=embed_model, dimensions=EMBEDDING_DIMENSIONS)
    return response.data[0].embedding


# ── Knowledge store (PostgreSQL + pgvector) ──────────────────────────

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


def create_knowledge_db(conn: psycopg.Connection) -> None:
    """Crea el catálogo de productos en PostgreSQL con pgvector e índices de texto completo."""
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)

    conn.execute("DROP TABLE IF EXISTS products")
    conn.execute(
        f"""
        CREATE TABLE products (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,
            price       REAL NOT NULL,
            description TEXT NOT NULL,
            embedding   vector({EMBEDDING_DIMENSIONS})
        )
        """
    )
    conn.execute("CREATE INDEX ON products USING GIN (to_tsvector('spanish', name || ' ' || description))")

    logger.info("[📚 Conocimiento] Generando embeddings para %d productos...", len(PRODUCTS))
    for product in PRODUCTS:
        text_for_embedding = f"{product['name']} - {product['category']}: {product['description']}"
        embedding = get_embedding(text_for_embedding)
        conn.execute(
            "INSERT INTO products (name, category, price, description, embedding) VALUES (%s, %s, %s, %s, %s)",
            (product["name"], product["category"], product["price"], product["description"], embedding),
        )

    conn.commit()
    logger.info("[📚 Conocimiento] Catálogo de productos cargado con embeddings.")


# ── Hybrid search SQL ────────────────────────────────────────────────

HYBRID_SEARCH_SQL = f"""
WITH semantic_search AS (
    SELECT id, RANK() OVER (ORDER BY embedding <=> %(embedding)s::vector({EMBEDDING_DIMENSIONS})) AS rank
    FROM products
    ORDER BY embedding <=> %(embedding)s::vector({EMBEDDING_DIMENSIONS})
    LIMIT 20
),
keyword_search AS (
    SELECT id, RANK() OVER (ORDER BY ts_rank_cd(to_tsvector('spanish', name || ' ' || description), query) DESC)
    FROM products, plainto_tsquery('spanish', %(query)s) query
    WHERE to_tsvector('spanish', name || ' ' || description) @@ query
    ORDER BY ts_rank_cd(to_tsvector('spanish', name || ' ' || description), query) DESC
    LIMIT 20
)
SELECT
    COALESCE(semantic_search.id, keyword_search.id) AS id,
    COALESCE(1.0 / (%(k)s + semantic_search.rank), 0.0) +
    COALESCE(1.0 / (%(k)s + keyword_search.rank), 0.0) AS score
FROM semantic_search
FULL OUTER JOIN keyword_search ON semantic_search.id = keyword_search.id
ORDER BY score DESC
LIMIT %(limit)s
"""


# ── Query rewriting prompt ───────────────────────────────────────────

QUERY_REWRITE_PROMPT = (
    "Eres un optimizador de consultas de búsqueda para un catálogo de productos de equipo al aire libre. "
    "Dada una conversación entre un usuario y un asistente, genera una sola "
    "consulta de búsqueda concisa que capture lo que el usuario está buscando ahora. "
    "La consulta debe ser autocontenida: no asumas que el motor de búsqueda tiene "
    "contexto de la conversación. Incluye detalles relevantes de mensajes previos "
    "que ayuden a aclarar la intención del usuario.\n\n"
    "Responde SOLO con la consulta de búsqueda, nada más."
)


# ── Context provider with query rewriting ────────────────────────────


class PostgresQueryRewriteProvider(ContextProvider):
    """Recupera conocimiento de productos usando consultas reescritas por LLM en multi-turno.

    En una conversación multi-turno, el último mensaje del usuario a menudo
    carece de contexto de turnos anteriores. Este proveedor le pide al LLM
    sintetizar toda la conversación en una sola consulta autocontenida
    antes de buscar en la base de conocimiento.

    Incluso en conversaciones de un solo turno, la reescritura ayuda a
    limpiar faltas de ortografía, frases largas y slang para mejorar la recuperación.
    """

    def __init__(
        self,
        conn: psycopg.Connection,
        rewrite_client: OpenAIChatClient,
        max_results: int = 3,
    ):
        super().__init__(source_id="postgres-knowledge-rewrite")
        self.conn = conn
        self.rewrite_client = rewrite_client
        self.max_results = max_results

    async def _rewrite_query(self, conversation_messages: list[Message]) -> str:
        """Pídele al LLM que genere una consulta de búsqueda a partir del historial.

        Args:
            conversation_messages: Conversación completa hasta ahora (mensajes de usuario + asistente).

        Returns:
            Una consulta de búsqueda concisa y autocontenida.
        """
        # Formatear conversación para el reescritor
        conversation_text = "\n".join(f"{msg.role}: {msg.text}" for msg in conversation_messages if msg.text)

        rewrite_messages = [
            Message(role="system", contents=[QUERY_REWRITE_PROMPT]),
            Message(role="user", contents=[f"Conversación:\n{conversation_text}"]),
        ]

        response = await self.rewrite_client.get_response(rewrite_messages)
        rewritten = response.text or ""
        return rewritten.strip().strip('"')

    def _search(self, query: str) -> list[dict]:
        """Ejecuta búsqueda híbrida (vector + texto completo) y devuelve productos coincidentes."""
        query_embedding = get_embedding(query)

        cursor = self.conn.execute(
            HYBRID_SEARCH_SQL,
            {"embedding": query_embedding, "query": query, "k": 60, "limit": self.max_results},
        )
        result_ids = [row[0] for row in cursor.fetchall()]
        if not result_ids:
            return []

        products = []
        for product_id in result_ids:
            row = self.conn.execute(
                "SELECT name, category, price, description FROM products WHERE id = %s",
                (product_id,),
            ).fetchone()
            if row:
                products.append({"name": row[0], "category": row[1], "price": row[2], "description": row[3]})
        return products

    def _format_results(self, results: list[dict]) -> str:
        """Formatea resultados como texto para el contexto del LLM."""
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
        """Reescribe la consulta usando el contexto y luego busca en la base de conocimiento."""
        # Recolectar todos los mensajes del contexto (historial + entrada actual)
        all_messages = list(context.get_messages()) + list(context.input_messages)
        # Filtrar mensajes de usuario/asistente con texto
        conversation = [msg for msg in all_messages if msg.role in ("user", "assistant") and msg.text]
        if not conversation:
            return

        # Siempre reescribir: limpia ortografía, reduce frases largas
        # e incorpora contexto de turnos previos.
        search_query = await self._rewrite_query(conversation)
        logger.info("[🔄 Query Rewrite] → '%s'", search_query[:80])

        results = self._search(search_query)
        if not results:
            logger.info("[📚 Conocimiento] No se encontraron productos para: %s", search_query)
            return

        logger.info("[📚 Conocimiento] Se encontraron %d producto(s)", len(results))

        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[self._format_results(results)])],
        )


# ── Setup ────────────────────────────────────────────────────────────


def setup_db() -> psycopg.Connection:
    """Conecta a PostgreSQL y carga la base de conocimiento."""
    conn = psycopg.connect(POSTGRES_URL)
    create_knowledge_db(conn)
    return conn


conn = setup_db()
knowledge_provider = PostgresQueryRewriteProvider(
    conn=conn,
    rewrite_client=chat_client,
)

agent = Agent(
    client=chat_client,
    instructions=(
        "Eres un asistente de compras de equipo para actividades al aire libre de la tienda 'TrailBuddy'. "
        "Responde las preguntas del cliente usando SOLO la información de productos proporcionada en el contexto. "
        "Si no se encuentran productos relevantes en el contexto, di que no tienes información sobre ese artículo. "
        "Incluye precios al recomendar productos."
    ),
    context_providers=[knowledge_provider],
)


async def main() -> None:
    """Demuestra reescritura de consulta en una conversación multi-turno.

    La conversación sigue el patrón de la diapositiva:
    1. Usuario pregunta por protección contra lluvia en senderos rocosos
    2. Agente recomienda productos (por ejemplo, botas, chaqueta)
    3. Usuario hace un seguimiento sobre situaciones con nieve

    Sin reescritura, buscar solo "situaciones con nieve" se pierde el contexto
    de chaquetas y botas. Con reescritura, el LLM sintetiza toda la conversación
    en algo como "chaquetas y botas protectoras para senderismo en nieve".
    """
    print("\n[bold]=== Recuperación de conocimiento con reescritura de consultas ===[/bold]")
    session = agent.create_session()

    # Turno 1: Usuario pide protección contra lluvia en senderos rocosos
    user_msg = "Necesito protección contra la lluvia en senderos rocosos."
    print(f"[blue]Usuario:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agente:[/green] {response.text}\n")

    # Turno 2: Seguimiento sobre situaciones con nieve
    # Sin reescritura, "situaciones con nieve" se pierde el contexto de botas/chaqueta
    user_msg = "¿Qué equipo similar tienen para situaciones con nieve?"
    print(f"[blue]Usuario:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agente:[/green] {response.text}\n")

    # Turno 3: Otro seguimiento para opciones más ligeras
    user_msg = "¿Algo más ligero que pueda llevar?"
    print(f"[blue]Usuario:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agente:[/green] {response.text}\n")

    conn.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())
