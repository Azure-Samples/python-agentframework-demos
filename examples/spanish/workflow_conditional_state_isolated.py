"""Workflow Escritor → Revisor con salidas estructuradas, estado y aislamiento de estado.

Demuestra: decisiones estructuradas del revisor, aristas condicionales,
bucles iterativos de revisión, manejo explícito de estado con
WorkflowContext.set_state/get_state y aislamiento por solicitud usando un
helper fábrica de workflow.

Enrutamiento:
    - decision == APPROVED        → publicador (ejecutor terminal con @executor)
    - decision == REVISION_NEEDED → editor → revisor (bucle iterativo)

Buena práctica de aislamiento de estado:
    Construye un workflow nuevo (y agentes nuevos) por cada tarea/solicitud
    llamando a create_workflow(...), para evitar fugas de estado del workflow
    y de hilos de agente entre ejecuciones independientes.

Ejecutar:
    uv run examples/spanish/workflow_conditional_state_isolated.py  (abre DevUI en http://localhost:8097)
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


def parse_review_decision(message: Any) -> ReviewDecision | None:
    """Parsea la salida estructurada del revisor desde AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewDecision.model_validate_json(message.agent_response.text)


# Funciones de condición — reciben el mensaje del ejecutor anterior.
def is_approved(message: Any) -> bool:
    """Enruta al publicador cuando la decisión estructurada es APPROVED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "APPROVED"


def needs_revision(message: Any) -> bool:
    """Enruta al editor cuando la decisión estructurada es REVISION_NEEDED."""
    result = parse_review_decision(message)
    return result is not None and result.decision == "REVISION_NEEDED"


def create_workflow(model_client: OpenAIChatClient):
    """Crea un workflow nuevo con estado aislado de agentes y workflow."""
    writer = Agent(
        client=model_client,
        name="Escritor",
        instructions=(
            "Eres un escritor de contenido conciso. "
            "Escribe un artículo corto (2-3 párrafos) claro y atractivo sobre el tema del usuario."
        ),
    )

    reviewer = Agent(
        client=model_client,
        name="Revisor",
        instructions=(
            "Eres un revisor de contenido estricto. Evalúa el borrador del escritor.\n"
            "Verifica que la publicación sea atractiva y que no suene demasiado generada por LLM.\n"
            "Restricciones de estilo/accesibilidad: no uses em dash (—) y no uses texto Unicode sofisticado.\n"
            "Devuelve una decisión estructurada usando este esquema: decision y feedback.\n"
            "Define decision=APPROVED si el borrador es claro, preciso y bien estructurado.\n"
            "Define decision=REVISION_NEEDED si necesita mejoras.\n"
            "En feedback, explica brevemente tu razonamiento y da cambios accionables cuando aplique."
        ),
        default_options={"response_format": ReviewDecision},
    )

    editor = Agent(
        client=model_client,
        name="Editor",
        instructions=(
            "Eres un editor habilidoso. "
            "Recibes un borrador del escritor seguido de la retroalimentación del revisor. "
            "Reescribe el borrador abordando todos los problemas señalados. "
            "Entrega solo el artículo mejorado."
            "Asegúrate de que el largo de la publicación final sea apropiado para la plataforma objetivo."
        ),
    )

    @executor(id="store_post_text")
    async def store_post_text(response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorResponse]) -> None:
        """Guarda el último texto de publicación en el estado y lo pasa aguas abajo."""
        ctx.set_state("post_text", response.agent_response.text.strip())
        await ctx.send_message(response)

    @executor(id="publisher")
    async def publisher(_response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
        """Publica el último texto aprobado desde el estado del workflow."""
        content = str(ctx.get_state("post_text", "")).strip()
        await ctx.yield_output(f"✅ Publicado:\n\n{content}")

    return (
        WorkflowBuilder(start_executor=writer, max_iterations=8)
        .add_edge(writer, store_post_text)
        .add_edge(store_post_text, reviewer)
        .add_edge(reviewer, publisher, condition=is_approved)
        .add_edge(reviewer, editor, condition=needs_revision)
        .add_edge(editor, store_post_text)
        .build()
    )


async def main():
    prompt = "Escribe una publicación de LinkedIn prediciendo 5 trabajos que los agentes de IA reemplazarán para diciembre de 2026."
    print(f"Prompt: {prompt}\n")

    # Construye un workflow nuevo por solicitud para aislar el estado.
    workflow = create_workflow(client)
    events = await workflow.run(prompt)

    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[create_workflow(client)], port=8097, auto_open=True)
    else:
        asyncio.run(main())
