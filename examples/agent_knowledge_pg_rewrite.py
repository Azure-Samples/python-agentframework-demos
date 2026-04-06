"""
Knowledge retrieval with query rewriting for multi-turn conversations.

Diagram:

 Conversation ──▶ "Suggest a search  ──▶ LLM ──▶ Rewritten  ──▶ Knowledge
  history          query based on               query           store
                   this conversation"

In a multi-turn conversation, the user's latest message often lacks
important context. For example:

  User: "I need protection from rain on rocky paths."
  Agent: "Check out our Down Jacket and Hiking Boots!"
  User: "What similar gear do you have for snowy situations?"

Searching only "What similar gear do you have for snowy situations?"
misses the context that the user is interested in jackets and boots.

A query rewriting step asks the LLM to synthesize the full conversation
into a single, self-contained search query — e.g., "protective jackets
and boots for hiking in snow" — which produces much better retrieval.

This example builds on agent_knowledge_postgres.py by adding an LLM-based
query rewriting step inside the context provider's ``before_run`` method.

Requires:
  - PostgreSQL with pgvector extension (see docker-compose.yml)
  - An embedding model (Azure OpenAI or OpenAI)
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

# ── OpenAI clients (chat + embeddings) ───────────────────────────────
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://admin:LocalPasswordOnly@db:5432/postgres")
EMBEDDING_DIMENSIONS = 256  # Smaller dimension for efficiency

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
    """Get an embedding vector for the given text."""
    response = embed_client.embeddings.create(input=text, model=embed_model, dimensions=EMBEDDING_DIMENSIONS)
    return response.data[0].embedding


# ── Knowledge store (PostgreSQL + pgvector) ──────────────────────────

PRODUCTS = [
    {
        "name": "TrailBlaze Hiking Boots",
        "category": "Footwear",
        "price": 149.99,
        "description": (
            "Waterproof hiking boots with Vibram soles, ankle support, "
            "and breathable Gore-Tex lining. Ideal for rocky trails and wet conditions."
        ),
    },
    {
        "name": "SummitPack 40L Backpack",
        "category": "Bags",
        "price": 89.95,
        "description": (
            "Lightweight 40-liter backpack with hydration sleeve, rain cover, "
            "and ergonomic hip belt. Great for day hikes and overnight trips."
        ),
    },
    {
        "name": "ArcticShield Down Jacket",
        "category": "Clothing",
        "price": 199.00,
        "description": (
            "800-fill goose down jacket rated to -20°F. "
            "Features a water-resistant shell, packable design, and adjustable hood."
        ),
    },
    {
        "name": "RiverRun Kayak Paddle",
        "category": "Water Sports",
        "price": 74.50,
        "description": (
            "Fiberglass kayak paddle with adjustable ferrule and drip rings. "
            "Lightweight at 28 oz, suitable for touring and recreational kayaking."
        ),
    },
    {
        "name": "TerraFirm Trekking Poles",
        "category": "Accessories",
        "price": 59.99,
        "description": (
            "Collapsible carbon-fiber trekking poles with cork grips and tungsten tips. "
            "Adjustable from 24 to 54 inches, with anti-shock springs."
        ),
    },
    {
        "name": "ClearView Binoculars 10x42",
        "category": "Optics",
        "price": 129.00,
        "description": (
            "Roof-prism binoculars with 10x magnification and 42mm objective lenses. "
            "Nitrogen-purged and waterproof. Ideal for birding and wildlife observation."
        ),
    },
    {
        "name": "NightGlow LED Headlamp",
        "category": "Lighting",
        "price": 34.99,
        "description": (
            "Rechargeable 350-lumen headlamp with red-light mode and adjustable beam. "
            "IPX6 waterproof rating, runs up to 40 hours on low."
        ),
    },
    {
        "name": "CozyNest Sleeping Bag",
        "category": "Camping",
        "price": 109.00,
        "description": (
            "Three-season mummy sleeping bag rated to 20°F. "
            "Synthetic insulation, compression sack included. Weighs 2.5 lbs."
        ),
    },
]


def create_knowledge_db(conn: psycopg.Connection) -> None:
    """Create the product catalog in PostgreSQL with pgvector and full-text search indexes."""
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
    conn.execute("CREATE INDEX ON products USING GIN (to_tsvector('english', name || ' ' || description))")

    logger.info("[📚 Knowledge] Generating embeddings for %d products...", len(PRODUCTS))
    for product in PRODUCTS:
        text_for_embedding = f"{product['name']} - {product['category']}: {product['description']}"
        embedding = get_embedding(text_for_embedding)
        conn.execute(
            "INSERT INTO products (name, category, price, description, embedding) VALUES (%s, %s, %s, %s, %s)",
            (product["name"], product["category"], product["price"], product["description"], embedding),
        )

    conn.commit()
    logger.info("[📚 Knowledge] Product catalog seeded with embeddings.")


# ── Hybrid search SQL ────────────────────────────────────────────────

HYBRID_SEARCH_SQL = f"""
WITH semantic_search AS (
    SELECT id, RANK() OVER (ORDER BY embedding <=> %(embedding)s::vector({EMBEDDING_DIMENSIONS})) AS rank
    FROM products
    ORDER BY embedding <=> %(embedding)s::vector({EMBEDDING_DIMENSIONS})
    LIMIT 20
),
keyword_search AS (
    SELECT id, RANK() OVER (ORDER BY ts_rank_cd(to_tsvector('english', name || ' ' || description), query) DESC)
    FROM products, plainto_tsquery('english', %(query)s) query
    WHERE to_tsvector('english', name || ' ' || description) @@ query
    ORDER BY ts_rank_cd(to_tsvector('english', name || ' ' || description), query) DESC
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
    "You are a search query optimizer for an outdoor gear product catalog. "
    "Given a conversation between a user and an assistant, generate a single "
    "concise search query that captures what the user is currently looking for. "
    "The query should be self-contained — do not assume the search engine has "
    "any conversation context. Include relevant details from earlier messages "
    "that help clarify the user's intent.\n\n"
    "Respond with ONLY the search query, nothing else."
)


# ── Context provider with query rewriting ────────────────────────────


class PostgresQueryRewriteProvider(ContextProvider):
    """Retrieves product knowledge using LLM-rewritten queries for multi-turn conversations.

    In a multi-turn conversation, the user's latest message often lacks
    important context from earlier turns. This provider asks the LLM to
    synthesize the full conversation into a single, self-contained search
    query before searching the knowledge base.

    Even for single-turn conversations, the rewrite step cleans up
    spelling mistakes, verbose phrasing, and slang for better retrieval.
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
        """Ask the LLM to produce a search query from the conversation history.

        Args:
            conversation_messages: The full conversation so far (user + assistant messages).

        Returns:
            A concise, self-contained search query.
        """
        # Format conversation for the rewriter
        conversation_text = "\n".join(f"{msg.role}: {msg.text}" for msg in conversation_messages if msg.text)

        rewrite_messages = [
            Message(role="system", contents=[QUERY_REWRITE_PROMPT]),
            Message(role="user", contents=[f"Conversation:\n{conversation_text}"]),
        ]

        response = await self.rewrite_client.get_response(rewrite_messages)
        rewritten = response.text or ""
        return rewritten.strip().strip('"')

    def _search(self, query: str) -> list[dict]:
        """Run hybrid search (vector + full-text) and return matching products."""
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
        """Format search results as a text block for the LLM context."""
        lines = ["Relevant product information from our catalog:\n"]
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
        """Rewrite the query using conversation context, then search the knowledge base."""
        # Collect all messages in context (history + current input)
        all_messages = list(context.get_messages()) + list(context.input_messages)
        # Filter to user/assistant messages with text content
        conversation = [msg for msg in all_messages if msg.role in ("user", "assistant") and msg.text]
        if not conversation:
            return

        # Always rewrite: cleans up spelling, condenses verbose phrasing,
        # and incorporates context from earlier turns in multi-turn conversations.
        search_query = await self._rewrite_query(conversation)
        logger.info("[🔄 Query Rewrite] → '%s'", search_query[:80])

        results = self._search(search_query)
        if not results:
            logger.info("[📚 Knowledge] No matching products found for: %s", search_query)
            return

        logger.info("[📚 Knowledge] Found %d matching product(s)", len(results))

        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[self._format_results(results)])],
        )


# ── Setup ────────────────────────────────────────────────────────────


def setup_db() -> psycopg.Connection:
    """Connect to PostgreSQL and seed the knowledge base."""
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
        "You are a helpful outdoor-gear shopping assistant for the store 'TrailBuddy'. "
        "Answer customer questions using ONLY the product information provided in the context. "
        "If no relevant products are found in the context, say you don't have information "
        "about that item. Include prices when recommending products."
    ),
    context_providers=[knowledge_provider],
)


async def main() -> None:
    """Demonstrate query rewriting in a multi-turn conversation.

    The conversation follows the pattern from the slide:
    1. User asks about rain protection on rocky paths
    2. Agent recommends products (e.g., boots, jacket)
    3. User asks a follow-up about snowy situations

    Without query rewriting, searching "what similar gear do you have for
    snowy situations?" misses the context of jackets and boots. With query
    rewriting, the LLM synthesizes the full conversation into something
    like "protective jackets and boots for hiking in snow".
    """
    print("\n[bold]=== Knowledge Retrieval with Query Rewriting ===[/bold]")
    session = agent.create_session()

    # Turn 1: User asks about rain protection on rocky paths
    user_msg = "I need protection from rain on rocky paths."
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 2: Follow-up about snowy situations
    # Without rewriting, "snowy situations" alone misses the boots/jacket context
    user_msg = "What similar gear do you have for snowy situations?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    # Turn 3: Another follow-up narrowing to lightweight options
    user_msg = "Anything lighter weight I could bring along?"
    print(f"[blue]User:[/blue] {user_msg}")
    response = await agent.run(user_msg, session=session)
    print(f"[green]Agent:[/green] {response.text}\n")

    conn.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())
