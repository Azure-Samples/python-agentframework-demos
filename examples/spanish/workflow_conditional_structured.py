"""Workflow Escritor → Revisor usando salidas estructuradas con aristas condicionales.

Demuestra: response_format para decisiones tipadas del revisor, aristas
condicionales y un nodo publicador terminal con @executor.

Este ejemplo contrasta directamente con workflow_conditional.py:
- Misma forma de branching con add_edge(..., condition=...)
- Mecanismo de decisión diferente (JSON tipado en vez de matching por cadena)

Enrutamiento:
    - decision == APPROVED        → publicador (ejecutor terminal con @executor)
    - decision == REVISION_NEEDED → editor (Agent terminal)

Ejecutar:
    uv run examples/spanish/workflow_conditional_structured.py  (abre DevUI en http://localhost:8096)
"""

import asyncio
import os
import sys
from typing import Any, Literal

from agent_framework import Agent, AgentExecutorResponse, WorkflowBuilder, WorkflowContext, executor
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel
from typing_extensions import Never

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

# Configura el cliente de chat según el proveedor de API
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


class ReviewDecision(BaseModel):
    """Decisión estructurada del revisor para enrutamiento condicional."""

    decision: Literal["APPROVED", "REVISION_NEEDED"]
    feedback: str
    post_text: str | None = None


# Helper de parseo para mantener pequeñas y explícitas las funciones de condición.
def parse_review_decision(message: Any) -> ReviewDecision | None:
    """Parsea la salida estructurada del revisor desde AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewDecision.model_validate_json(message.agent_response.text)


def is_approved(message: Any) -> bool:
    """Enruta al publicador cuando la decisión estructurada es APPROVED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "APPROVED"


def needs_revision(message: Any) -> bool:
    """Enruta al editor cuando la decisión estructurada es REVISION_NEEDED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "REVISION_NEEDED"


writer = Agent(
    client=client,
    name="Escritor",
    instructions=(
        "Eres un escritor de contenido conciso. "
        "Escribe un artículo corto (2-3 párrafos) claro y atractivo sobre el tema del usuario."
    ),
)

reviewer = Agent(
    client=client,
    name="Revisor",
    instructions=(
        "Eres un revisor de contenido estricto. Evalúa el borrador del escritor. "
        "Si el borrador está listo, define decision=APPROVED e incluye la publicación lista para publicar en post_text. "
        "Si necesita cambios, define decision=REVISION_NEEDED y entrega feedback accionable."
    ),
    default_options={"response_format": ReviewDecision},
)

editor = Agent(
    client=client,
    name="Editor",
    instructions=(
        "Eres un editor habilidoso. "
        "Recibes un borrador del escritor seguido de la retroalimentación del revisor. "
        "Reescribe el borrador abordando todos los problemas señalados. "
        "Entrega solo el artículo mejorado."
    ),
)


@executor(id="publisher")
async def publisher(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """Publica contenido desde la salida estructurada del revisor."""
    result = parse_review_decision(response)
    if result is None:
        await ctx.yield_output("✅ Publicado:\n\n(No se pudo parsear la salida estructurada del revisor.)")
        return

    content = (result.post_text or "").strip()
    if not content:
        content = "(El revisor aprobó pero no incluyó post_text.)"

    await ctx.yield_output(f"✅ Publicado:\n\n{content}")


workflow = (
    WorkflowBuilder(start_executor=writer)
    .add_edge(writer, reviewer)
    .add_edge(reviewer, publisher, condition=is_approved)
    .add_edge(reviewer, editor, condition=needs_revision)
    .build()
)


async def main():
    prompt = "Escribe una publicación de LinkedIn prediciendo los 5 trabajos que los agentes de IA reemplazarán para diciembre de 2026."
    print(f"Solicitud: {prompt}\n")
    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8096, auto_open=True)
    else:
        asyncio.run(main())
