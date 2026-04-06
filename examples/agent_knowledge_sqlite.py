"""
Knowledge retrieval (RAG) via a custom context provider.

Diagram:

 Input ──▶ Agent ──────────────────▶ LLM ──▶ Response
             │                        ▲
             │  search with input     │ relevant knowledge
             ▼                        │
         ┌────────────┐               │
         │ Knowledge  │───────────────┘
         │   store    │
         │ (SQLite)   │
         └────────────┘

The agent retrieves knowledge from a SQLite FTS5 database *before*
asking the LLM to respond. Because the agent always needs domain-specific
knowledge to ground its answers, a deterministic search step is more
efficient and reliable than asking the LLM to decide to call a tool.

This example seeds a small product-catalog knowledge base and uses a
custom ContextProvider to inject matching rows into the LLM context.
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

# ── OpenAI client ────────────────────────────────────────────────────
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


# ── Knowledge store (SQLite + FTS5) ─────────────────────────────────

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


def create_knowledge_db(db_path: str) -> sqlite3.Connection:
    """Create (or re-create) the product catalog in SQLite with an FTS5 index."""
    conn = sqlite3.connect(db_path)

    # Drop existing tables so we always start fresh
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

    # Build a full-text search index on name, category, and description
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


# ── Custom context provider for knowledge retrieval ──────────────────


class SQLiteKnowledgeProvider(ContextProvider):
    """Retrieves relevant product knowledge from SQLite FTS5 before each LLM call.

    This follows the "knowledge retrieval" pattern where the agent deterministically
    searches a knowledge store *before* the LLM runs, rather than relying on
    the LLM to decide whether to call a search tool. This ensures the model
    always has domain-specific context to ground its response.
    """

    def __init__(self, db_conn: sqlite3.Connection, max_results: int = 3):
        super().__init__(source_id="sqlite-knowledge")
        self.db_conn = db_conn
        self.max_results = max_results

    def _search(self, query: str) -> list[dict]:
        """Run an FTS5 query and return matching products."""
        # Extract words, drop short ones (len <= 2 catches "a", "an", "is", etc.)
        words = re.findall(r"[a-zA-Z]+", query)
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
            logger.debug("FTS query failed for: %s", fts_query, exc_info=True)
            return []

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
        """Search the knowledge base with the user's latest message and inject results."""
        user_text = next(
            (msg.text for msg in reversed(context.input_messages) if msg.role == "user" and msg.text), None
        )
        if not user_text:
            return

        results = self._search(user_text)
        if not results:
            logger.info("[📚 Knowledge] No matching products found for: %s", user_text)
            return

        logger.info("[📚 Knowledge] Found %d matching product(s) for: %s", len(results), user_text)

        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[self._format_results(results)])],
        )


# ── Agent setup ──────────────────────────────────────────────────────

DB_PATH = ":memory:"  # In-memory DB — no file cleanup needed

# Create and seed the knowledge database
db_conn = create_knowledge_db(DB_PATH)
knowledge_provider = SQLiteKnowledgeProvider(db_conn=db_conn)

agent = Agent(
    client=client,
    instructions=(
        "You are a helpful outdoor-gear shopping assistant for the store 'TrailBuddy'. "
        "Answer customer questions using ONLY the product information provided in the context. "
        "If no relevant products are found in the context, say you don't have information "
        "about that item. Include prices when recommending products."
    ),
    context_providers=[knowledge_provider],
)


async def main() -> None:
    """Demonstrate the knowledge retrieval (RAG) pattern with several queries."""
    # Query 1: Should match hiking boots and trekking poles
    print("\n[bold]=== Knowledge Retrieval (RAG) Demo ===[/bold]")

    print("[blue]User:[/blue] I'm planning a hiking trip. What boots and poles do you recommend?")
    response = await agent.run("I'm planning a hiking trip. What boots and poles do you recommend?")
    print(f"[green]Agent:[/green] {response.text}\n")

    # Query 2: No match expected — demonstrates graceful "no knowledge" handling
    print("[blue]User:[/blue] Do you have any surfboards?")
    response = await agent.run("Do you have any surfboards?")
    print(f"[green]Agent:[/green] {response.text}\n")

    db_conn.close()

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())
