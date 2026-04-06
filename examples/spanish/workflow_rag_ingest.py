"""Pipeline de ingesta para RAG usando ejecutores Python puros.

Demuestra: subclases de Executor, @handler, WorkflowContext con tipos de datos
y WorkflowBuilder con aristas explícitas — sin agentes de IA.

Pipeline:
    Extract → Chunk → Embed

Ejecutar:
    uv run examples/spanish/workflow_rag_ingest.py
    uv run examples/spanish/workflow_rag_ingest.py --devui  (abre DevUI en http://localhost:8090)

En DevUI, escribe un nombre de archivo relativo a la carpeta examples/, por ejemplo: sample_document.pdf
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
EMBEDDING_DIMENSIONS = 256  # Dimensiones reducidas para mayor eficiencia

# Configura el cliente de embeddings según el proveedor de API
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
    """Un fragmento de texto junto con su vector de embedding."""

    text: str
    vector: list[float] = field(default_factory=list)


class ExtractExecutor(Executor):
    """Convierte un archivo local a texto markdown."""

    @handler
    async def extract(self, path: str, ctx: WorkflowContext[str]) -> None:
        """Convierte el archivo en la ruta dada a markdown.

        Acepta una ruta absoluta o un nombre de archivo relativo a la carpeta examples
        (p. ej. ``sample_document.pdf``). Las comillas que rodean la entrada se eliminan automáticamente.
        WorkflowContext[str] indica que este nodo envía un str al siguiente nodo.
        """
        path = path.strip("'\"")
        resolved = Path(path) if Path(path).is_absolute() else Path(__file__).parent.parent / path
        result = MarkItDown().convert(str(resolved))
        await ctx.send_message(result.text_content)


class ChunkExecutor(Executor):
    """Divide el markdown en párrafos, conservando solo los sustanciales."""

    @handler
    async def chunk(self, markdown: str, ctx: WorkflowContext[list[str]]) -> None:
        """Divide por líneas en blanco y filtra encabezados y fragmentos cortos.

        WorkflowContext[list[str]] indica que este nodo envía una list[str] aguas abajo.
        """
        paragraphs = markdown.split("\n\n")
        chunks = [p.strip() for p in paragraphs if len(p.strip()) >= 80 and not p.strip().startswith("#")]
        logger.info(f"→ {len(chunks)} fragmentos extraídos")
        await ctx.send_message(chunks)


class EmbedExecutor(Executor):
    """Genera el embedding de cada fragmento con el modelo de OpenAI configurado."""

    @handler
    async def embed(self, chunks: list[str], ctx: WorkflowContext[Never, list[EmbeddedChunk]]) -> None:
        """Llama a la API de embeddings para cada fragmento y entrega los resultados.

        WorkflowContext[Never, list[EmbeddedChunk]] indica que este nodo terminal
        produce la salida del workflow pero no reenvía mensajes.
        """

        embedded = []
        for chunk in chunks:
            response = embed_client.embeddings.create(input=chunk, model=embed_model, dimensions=EMBEDDING_DIMENSIONS)
            embedded.append(EmbeddedChunk(text=chunk, vector=response.data[0].embedding))
        logger.info(f"→ {len(embedded)} fragmentos embebidos ({EMBEDDING_DIMENSIONS}d cada uno)")
        await ctx.yield_output(embedded)


# Crea las instancias de los ejecutores
extract = ExtractExecutor(id="extract")
chunk = ChunkExecutor(id="chunk")
embed = EmbedExecutor(id="embed")

# Construye el workflow: Extract → Chunk → Embed
workflow = WorkflowBuilder(start_executor=extract).add_edge(extract, chunk).add_edge(chunk, embed).build()


async def main():
    pdf_path = str(Path(__file__).parent.parent / "sample_document.pdf")
    logger.info("Procesando: %s", pdf_path)
    events = await workflow.run(pdf_path)
    outputs = events.get_outputs()
    for result in outputs:
        logger.info(f"{len(result)} fragmentos embebidos:")
        for chunk in result:
            preview = chunk.text[:80].replace("\n", " ")
            logger.info(f"  [{len(chunk.vector)}d] {preview}…")


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8090, auto_open=True)
    else:
        asyncio.run(main())
