"""Workflow Escritor → Revisor con enrutamiento de rama y convergencia.

Demuestra: ejecutores Agent, aristas condicionales y una forma de grafo que
se divide y vuelve a converger: el Revisor enruta directo al Publicador
(aprobado) o pasa por el Editor, y ambas rutas convergen antes del Resumidor.

Ejecutar:
    uv run examples/spanish/workflow_converge.py
    uv run examples/spanish/workflow_converge.py --devui  (abre DevUI en http://localhost:8093)
"""

import asyncio
import os
import sys
from typing import Any

from agent_framework import Agent, AgentExecutorResponse, Message, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel

# Configura el cliente de OpenAI según el entorno
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

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


class ReviewResult(BaseModel):
    """Evaluación estructurada con puntajes y retroalimentación."""

    score: int
    feedback: str
    clarity: int
    completeness: int
    accuracy: int
    structure: int


def parse_review_result(message: Any) -> ReviewResult | None:
    """Parsea la salida estructurada del revisor desde AgentExecutorResponse."""
    if not isinstance(message, AgentExecutorResponse):
        return None

    return ReviewResult.model_validate_json(message.agent_response.text)


def is_approved(message: Any) -> bool:
    """Verifica si el contenido está aprobado (alta calidad)."""
    result = parse_review_result(message)
    return result is not None and result.score >= 80


def needs_editing(message: Any) -> bool:
    """Enruta al editor cuando la calidad está debajo del umbral."""
    result = parse_review_result(message)
    return result is not None and result.score < 80


writer = Agent(
    client=client,
    name="Writer",
    instructions=(
        "Eres un excelente escritor de contenido. "
        "Crea contenido claro y atractivo basado en la solicitud del usuario. "
        "Enfócate en la claridad, precisión y estructura adecuada."
    ),
)


reviewer = Agent(
    client=client,
    name="Reviewer",
    instructions=(
        "Eres un experto revisor de contenido. "
        "Evalúa el contenido del escritor basándote en:\n"
        "1. Claridad - ¿Es fácil de entender?\n"
        "2. Completitud - ¿Aborda completamente el tema?\n"
        "3. Precisión - ¿Es correcta la información?\n"
        "4. Estructura - ¿Está bien organizado?\n\n"
        "Devuelve un objeto JSON con:\n"
        "- score: calidad general (0-100)\n"
        "- feedback: retroalimentación concisa y accionable\n"
        "- clarity, completeness, accuracy, structure: puntajes individuales (0-100)"
    ),
    default_options={"response_format": ReviewResult},
)


editor = Agent(
    client=client,
    name="Editor",
    instructions=(
        "Eres un editor habilidoso. "
        "Recibirás contenido junto con retroalimentación de revisión. "
        "Mejora el contenido abordando todos los problemas mencionados en la retroalimentación. "
        "Mantén la intención original mientras mejoras la claridad, completitud, precisión y estructura."
    ),
)


publisher = Agent(
    client=client,
    name="Publisher",
    instructions=(
        "Eres un agente de publicación. "
        "Recibes contenido aprobado o editado. "
        "Formatea el contenido para publicación con encabezados y estructura adecuados."
    ),
)

summarizer = Agent(
    client=client,
    name="Summarizer",
    instructions=(
        "Eres un agente resumidor. "
        "Crea un informe de publicación final que incluya:\n"
        "1. Un breve resumen del contenido publicado\n"
        "2. El camino del flujo de trabajo seguido (aprobación directa o editado)\n"
        "3. Aspectos destacados y conclusiones clave\n"
        "Mantén la concisión y el profesionalismo."
    ),
)


workflow = (
    WorkflowBuilder(
        name="ContentConverge",
        start_executor=writer,
        description="Rutas condicionales que convergen antes del resumen final.",
    )
    .add_edge(writer, reviewer)
    .add_edge(reviewer, publisher, condition=is_approved)
    .add_edge(reviewer, editor, condition=needs_editing)
    .add_edge(editor, publisher)
    .add_edge(publisher, summarizer)
    .build()
)


async def main():
    prompt = 'Escribe una publicación de LinkedIn de un párrafo: "El error de workflow de IA que casi todos los equipos cometen."'
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    outputs = events.get_outputs()

    for output in outputs:
        if not isinstance(output, AgentExecutorResponse):
            print(output)
            continue

        final_message = Message(role="assistant", contents=[output.agent_response.text])
        print(f"[{output.executor_id}]\n{final_message.text}\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8093, auto_open=True)
    else:
        asyncio.run(main())
