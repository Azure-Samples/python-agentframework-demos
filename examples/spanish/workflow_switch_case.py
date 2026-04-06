"""Enrutador de mensajes de clientes con salidas estructuradas y aristas switch-case.

Demuestra: response_format= para salidas estructuradas confiables, @executor
para un nodo convertidor y add_switch_case_edge_group para enrutamiento múltiple.

Un agente Clasificador usa un modelo Pydantic como response_format para que
la categoría siempre sea un valor válido y tipado — sin matching frágil de cadenas.
Un ejecutor convertidor extrae el resultado estructurado; luego las aristas switch-case
enrutan a un manejador especializado para cada categoría.

Pipeline:
    Clasificador → extract_category → [Case: Question   → handle_question ]
                                    → [Case: Complaint  → handle_complaint]
                                    → [Default          → handle_feedback ]

Contraste con workflow_conditional.py: las salidas estructuradas hacen que la lógica
de ramificación sea explícita, tipada y fácil de extender.

Ejecutar:
    uv run examples/spanish/workflow_switch_case.py  (abre DevUI en http://localhost:8095)
"""

import asyncio
import os
import sys
from typing import Any, Literal

from agent_framework import Agent, AgentExecutorResponse, Case, Default, WorkflowBuilder, WorkflowContext, executor
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


# Modelo Pydantic usado como response_format — el LLM debe devolver JSON válido
# que coincida con este esquema, garantizando que la categoría siempre sea uno de los tres literales.
class ClassifyResult(BaseModel):
    """Resultado de clasificación estructurado del agente Clasificador."""

    category: Literal["Question", "Complaint", "Feedback"]
    original_message: str
    reasoning: str


# El agente clasificador usa response_format= para asegurar una salida estructurada.
# Esto es más confiable que pedirle al modelo que comience con una señal de texto.
classifier = Agent(
    client=client,
    name="Clasificador",
    instructions=(
        "Eres un clasificador de mensajes de clientes. "
        "Clasifica el mensaje entrante del cliente en exactamente una categoría: "
        "Question, Complaint o Feedback. "
        "Devuelve un objeto JSON con category, original_message y reasoning."
    ),
    default_options={"response_format": ClassifyResult},
)


# Ejecutor convertidor: analiza la respuesta JSON del agente en un ClassifyResult tipado
# y lo reenvía. Las condiciones switch-case inspeccionarán este objeto tipado.
@executor(id="extract_category")
async def extract_category(response: AgentExecutorResponse, ctx: WorkflowContext[ClassifyResult]) -> None:
    """Analiza la salida JSON estructurada del clasificador y la envía aguas abajo."""
    result = ClassifyResult.model_validate_json(response.agent_response.text)
    print(f"→ Clasificado como: {result.category} — {result.reasoning}")
    await ctx.send_message(result)


# Funciones de condición para el enrutamiento switch-case.
# Cada una recibe el ClassifyResult enviado por extract_category.
def is_question(msg: Any) -> bool:
    return isinstance(msg, ClassifyResult) and msg.category == "Question"


def is_complaint(msg: Any) -> bool:
    return isinstance(msg, ClassifyResult) and msg.category == "Complaint"


# Ejecutores terminales de manejo — uno por rama.
# Cada uno recibe el ClassifyResult y entrega una cadena de respuesta formateada.
@executor(id="handle_question")
async def handle_question(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Enruta una pregunta al equipo de Q&A."""
    await ctx.yield_output(
        f"❓ Pregunta enrutada al equipo de Q&A\n\n"
        f"Mensaje: {result.original_message}\n"
        f"Motivo: {result.reasoning}"
    )


@executor(id="handle_complaint")
async def handle_complaint(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Escala una queja al equipo de soporte."""
    await ctx.yield_output(
        f"⚠️  Queja escalada al equipo de soporte\n\n"
        f"Mensaje: {result.original_message}\n"
        f"Motivo: {result.reasoning}"
    )


@executor(id="handle_feedback")
async def handle_feedback(result: ClassifyResult, ctx: WorkflowContext[Never, str]) -> None:
    """Reenvía el feedback al equipo de producto."""
    await ctx.yield_output(
        f"💬 Feedback reenviado al equipo de producto\n\n"
        f"Mensaje: {result.original_message}\n"
        f"Motivo: {result.reasoning}"
    )


# Construye el workflow.
# add_switch_case_edge_group evalúa los casos en orden y toma el primero que coincida.
# Default captura todo lo que no coincida con un Case explícito.
workflow = (
    WorkflowBuilder(start_executor=classifier)
    .add_edge(classifier, extract_category)
    .add_switch_case_edge_group(
        extract_category,
        [
            Case(condition=is_question, target=handle_question),
            Case(condition=is_complaint, target=handle_complaint),
            Default(target=handle_feedback),
        ],
    )
    .build()
)


async def main():
    message = "¿Cómo puedo restablecer mi contraseña?"
    print(f"Mensaje del cliente: {message}\n")
    events = await workflow.run(message)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8095, auto_open=True)
    else:
        asyncio.run(main())
