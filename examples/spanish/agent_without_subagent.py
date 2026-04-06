"""Inflado de contexto sin subagentes.

Cuando un agente usa herramientas que regresan salidas grandes (contenido de
archivos, resultados de búsqueda, filas de base de datos), toda esa data cruda
se acumula en la ventana de contexto del agente. Tras múltiples llamadas a
herramientas, esto infla el contexto, aumenta el costo y puede degradar el
rendimiento.

Este ejemplo demuestra el problema: un solo agente lee y busca archivos fuente
directamente. Cada línea de código fuente fluye hacia el contexto del agente
junto con la conversación.

Diagrama:

 agent.run("pregunta del usuario")
 │
 ▼
 ┌──────────────────────────────────────────────────┐
 │           Agente de Investigación de Código      │
 │                                                  │
 │  1. Llama list_project_files() → lista completa  │
 │  2. Llama read_project_file() → contenido        │
 │     completo agregado al contexto (N veces)      │
 │  3. Llama search_project_files() → todas las     │
 │     líneas coincidentes agregadas al contexto    │
 │  4. Genera respuesta desde un contexto inflado   │
 └──────────────────────────────────────────────────┘
 │
 ▼
 respuesta (el agente vio TODO el contenido crudo)

Compara con agent_with_subagent.py para ver cómo los subagentes solucionan esto.
"""

import asyncio
import glob
import logging
import os
import sys
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
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
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4"))

# ── Raíz del proyecto para herramientas de archivos ──────────────────
PROJECT_DIR = os.path.join(os.path.dirname(__file__))


# ── Herramientas ─────────────────────────────────────────────────────


@tool
def list_project_files(
    directory: Annotated[
        str, Field(description="Relative directory path within the examples folder, e.g. '.' or 'spanish'.")
    ],
) -> str:
    """Lista todos los archivos en el directorio indicado dentro de la carpeta examples."""
    logger.info("[📂 Herramienta] list_project_files('%s')", directory)
    target = os.path.join(PROJECT_DIR, directory)
    if not os.path.isdir(target):
        return f"Error: no se encontró el directorio '{directory}'."
    entries = sorted(os.listdir(target))
    return "\n".join(entries)


@tool
def read_project_file(
    filepath: Annotated[
        str, Field(description="Relative file path within the examples folder, e.g. 'agent_middleware.py'.")
    ],
) -> str:
    """Lee y devuelve el contenido completo de un archivo dentro de la carpeta examples."""
    logger.info("[📄 Herramienta] read_project_file('%s')", filepath)
    target = os.path.join(PROJECT_DIR, filepath)
    if not os.path.isfile(target):
        return f"Error: no se encontró el archivo '{filepath}'."
    with open(target) as f:
        return f.read()


@tool
def search_project_files(
    query: Annotated[
        str, Field(description="Text to search for (case-insensitive) across all .py files in the examples folder.")
    ],
) -> str:
    """Busca en todos los .py dentro de examples las líneas que contengan el texto."""
    logger.info("[🔍 Herramienta] search_project_files('%s')", query)
    query_lower = query.lower()
    results: list[str] = []
    for fpath in sorted(glob.glob(os.path.join(PROJECT_DIR, "*.py"))):
        relpath = os.path.relpath(fpath, PROJECT_DIR)
        with open(fpath) as f:
            for lineno, line in enumerate(f, 1):
                if query_lower in line.lower():
                    results.append(f"{relpath}:{lineno}: {line.rstrip()}")
    if not results:
        return f"No se encontraron coincidencias para '{query}'."
    if len(results) > 50:
        return "\n".join(results[:50]) + f"\n... ({len(results) - 50} coincidencias más truncadas)"
    return "\n".join(results)


# ── Agent ────────────────────────────────────────────────────────────

agent = Agent(
    name="coding-assistant",
    client=client,
    instructions=(
        "Eres un asistente de programación útil. Respondes preguntas sobre bases de código, "
        "explicas patrones y ayudas a devs a entender el código. Usa las herramientas disponibles "
        "para listar, leer y buscar archivos Python del proyecto, y luego da una respuesta clara "
        "y bien organizada."
    ),
    tools=[list_project_files, read_project_file, search_project_files],
)

# ── Query ────────────────────────────────────────────────────────────

USER_QUERY = (
    "¿Qué patrones distintos de middleware se usan en este proyecto? Lee los archivos relevantes para averiguarlo."
)


async def main() -> None:
    """Ejecuta una consulta y registra el uso de tokens."""
    print("\n[bold]=== Investigación de Código SIN Subagentes ===[/bold]")
    print("[dim]Todo el contenido de archivos fluye directo a la ventana de contexto del agente.[/dim]\n")

    print(f"[blue]Usuario:[/blue] {USER_QUERY}")
    response = await agent.run(USER_QUERY)
    print(f"[green]Asistente:[/green] {response.text}\n")

    # Uso de tokens
    usage = response.usage_details or {}
    input_t = usage.get("input_token_count", 0) or 0
    output_t = usage.get("output_token_count", 0) or 0
    total_t = usage.get("total_token_count", 0) or 0

    print("[bold]── Uso de tokens ──[/bold]")
    print(f"[yellow]  Tokens del asistente:[/yellow]  input={input_t:,}  output={output_t:,}  total={total_t:,}")
    print()
    print("[dim]Todo el contenido crudo de archivos quedó en la ventana de contexto del agente.[/dim]")
    print("[dim]Compara con agent_with_subagent.py para ver el aislamiento de contexto en acción.[/dim]\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[agent], auto_open=True)
    else:
        asyncio.run(main())
