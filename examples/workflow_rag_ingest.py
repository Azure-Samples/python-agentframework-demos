"""RAG ingestion pipeline using plain Python executors.

Demonstrates: Executor subclasses, @handler, typed WorkflowContext, and
WorkflowBuilder with explicit edges — no AI agents involved.

Pipeline:
    Extract → Chunk → Embed

Run:
    uv run examples/workflow_rag_ingest.py
    uv run examples/workflow_rag_ingest.py --devui  (opens DevUI at http://localhost:8090)

In the DevUI, enter a filename relative to the examples/ folder, e.g.: sample_document.pdf
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from markitdown import MarkItDown
from openai import OpenAI
from rich.logging import RichHandler
from typing_extensions import Never

log_handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[log_handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")
EMBEDDING_DIMENSIONS = 256  # Smaller dimension for efficiency

# Configure the embedding client based on the API host
if API_HOST == "azure":
    sync_credential = DefaultAzureCredential()
    sync_token_provider = get_bearer_token_provider(sync_credential, "https://cognitiveservices.azure.com/.default")
    embed_client = OpenAI(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=sync_token_provider(),
    )
    embed_model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
else:
    embed_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    embed_model = "text-embedding-3-small"


@dataclass
class EmbeddedChunk:
    """A text chunk paired with its embedding vector."""

    text: str
    vector: list[float] = field(default_factory=list)


class ExtractExecutor(Executor):
    """Convert a local file to plain markdown text."""

    @handler
    async def extract(self, path: str, ctx: WorkflowContext[str]) -> None:
        """Convert the file at the given path to markdown.

        Accepts an absolute path or a filename relative to the examples folder
        (e.g. ``sample_document.pdf``). Surrounding quotes are stripped automatically.
        WorkflowContext[str] means this node sends a str to the next node.
        """
        path = path.strip("'\"")
        resolved = Path(path) if Path(path).is_absolute() else Path(__file__).parent.parent / path
        result = MarkItDown().convert(str(resolved))
        await ctx.send_message(result.text_content)


class ChunkExecutor(Executor):
    """Split markdown into paragraphs, keeping only substantive ones."""

    @handler
    async def chunk(self, markdown: str, ctx: WorkflowContext[list[str]]) -> None:
        """Split on blank lines and filter out headings and short fragments.

        WorkflowContext[list[str]] means this node sends a list[str] downstream.
        """
        paragraphs = markdown.split("\n\n")
        chunks = [p.strip() for p in paragraphs if len(p.strip()) >= 80 and not p.strip().startswith("#")]
        logger.info(f"→ {len(chunks)} chunks extracted")
        await ctx.send_message(chunks)


class EmbedExecutor(Executor):
    """Embed each chunk with the configured OpenAI embedding model."""

    @handler
    async def embed(self, chunks: list[str], ctx: WorkflowContext[Never, list[EmbeddedChunk]]) -> None:
        """Call the embeddings API for each chunk and yield the results.

        WorkflowContext[Never, list[EmbeddedChunk]] means this terminal node
        yields workflow output but does not forward messages further.
        """

        embedded = []
        for chunk in chunks:
            response = embed_client.embeddings.create(input=chunk, model=embed_model, dimensions=EMBEDDING_DIMENSIONS)
            embedded.append(EmbeddedChunk(text=chunk, vector=response.data[0].embedding))
        logger.info(f"→ {len(embedded)} chunks embedded ({EMBEDDING_DIMENSIONS}d each)")
        await ctx.yield_output(embedded)


# Create executor instances
extract = ExtractExecutor(id="extract")
chunk = ChunkExecutor(id="chunk")
embed = EmbedExecutor(id="embed")

# Build the workflow: Extract → Chunk → Embed
workflow = WorkflowBuilder(start_executor=extract).add_edge(extract, chunk).add_edge(chunk, embed).build()


async def main():
    pdf_path = str(Path(__file__).parent / "sample_document.pdf")
    logger.info("Processing: %s", pdf_path)
    events = await workflow.run(pdf_path)
    outputs = events.get_outputs()
    for result in outputs:
        logger.info(f"Embedded {len(result)} chunks:")
        for chunk in result:
            preview = chunk.text[:80].replace("\n", " ")
            logger.info(f"  [{len(chunk.vector)}d] {preview}…")


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8090, auto_open=True)
    else:
        asyncio.run(main())
