"""Workflow de planificación de viajes con human-in-the-loop vía solicitudes y respuestas.

Demuestra: ctx.request_info(), @response_handler, salida estructurada del agente,
y manejo del bucle HITL desde el código de la aplicación.

El usuario comienza con una solicitud de viaje vaga como "Quiero ir a algún lugar cálido."
El agente planificador de viajes hace preguntas de clarificación una a la vez (destino,
presupuesto, intereses, fechas). Después de cada pregunta, el workflow pausa y espera
la respuesta del humano. Una vez que el agente tiene suficiente información, produce
un itinerario final.

Ejecutar:
    uv run examples/spanish/workflow_hitl_requests_structured.py
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Literal

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")

# Configura el cliente según el host de la API
async_credential = None
if API_HOST == "azure":
    async_credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model_id=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
    )
elif API_HOST == "github":
    client = OpenAIChatClient(
        base_url="https://models.github.ai/inference",
        api_key=os.environ["GITHUB_TOKEN"],
        model_id=os.getenv("GITHUB_MODEL", "openai/gpt-5-mini"),
    )
else:
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    )


# --- Modelos de salida estructurada ---


class PlannerOutput(BaseModel):
    """Salida estructurada del agente planificador de viajes."""

    status: Literal["need_info", "complete"]
    question: str | None = None
    itinerary: str | None = None


# --- Dataclass de solicitud HITL ---


@dataclass
class UserPrompt:
    """Solicitud enviada al humano cuando el agente necesita más información."""

    message: str


# --- Executor que coordina turnos entre agente y humano ---


class TripCoordinator(Executor):
    """Coordina turnos entre el agente planificador de viajes y el humano.

    - Después de cada respuesta del agente, verifica si se necesita más información.
    - Si es así, solicita entrada del humano vía ctx.request_info().
    - Si el agente tiene suficiente información, produce el itinerario final.
    """

    def __init__(self, agent_id: str, id: str = "trip_coordinator"):
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def start(self, request: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Inicia el primer turno del agente con la solicitud vaga del usuario."""
        user_msg = Message("user", text=request)
        await ctx.send_message(
            AgentExecutorRequest(messages=[user_msg], should_respond=True),
            target_id=self._agent_id,
        )

    @handler
    async def on_agent_response(self, result: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Maneja la respuesta estructurada del agente."""
        # Parsear la salida estructurada del texto (AgentResponse.value puede ser None
        # en workflows con streaming porque response_format no se propaga).
        output = PlannerOutput.model_validate_json(result.agent_response.text)

        if output.status == "need_info" and output.question:
            # Pausa y pregunta al humano
            await ctx.request_info(
                request_data=UserPrompt(message=output.question),
                response_type=str,
            )
        else:
            await ctx.yield_output(output.itinerary or "No se generó itinerario.")

    @response_handler
    async def on_human_answer(
        self,
        original_request: UserPrompt,
        answer: str,
        ctx: WorkflowContext[AgentExecutorRequest, str],
    ) -> None:
        """Reenvía la respuesta del humano al agente."""
        user_msg = Message("user", text=answer)
        await ctx.send_message(
            AgentExecutorRequest(messages=[user_msg], should_respond=True),
            target_id=self._agent_id,
        )


# --- Principal ---


async def main() -> None:
    """Ejecuta el workflow HITL del planificador de viajes."""
    planner_agent = Agent(
        name="TripPlanner",
        instructions=(
            "Eres un planificador de viajes servicial. El usuario tiene una idea de viaje vaga y necesitas "
            "recopilar suficientes detalles para crear un itinerario personalizado.\n"
            "Haz preguntas de clarificación UNA A LA VEZ sobre: preferencias de destino, fechas de viaje, "
            "presupuesto, intereses/actividades y tamaño del grupo.\n"
            "Una vez que tengas suficiente información (al menos destino, fechas y presupuesto), "
            'produce un itinerario final.\n\n'
            "DEBES devolver SOLO un objeto JSON que coincida con este esquema:\n"
            '  {"status": "need_info", "question": "tu pregunta aquí"}\n'
            "  O\n"
            '  {"status": "complete", "itinerary": "tu itinerario completo aquí"}\n'
            "Sin explicaciones ni texto adicional fuera del JSON."
        ),
        client=client,
        default_options={"response_format": PlannerOutput},
    )

    coordinator = TripCoordinator(agent_id="TripPlanner")

    workflow = (
        WorkflowBuilder(start_executor=coordinator)
        .add_edge(coordinator, planner_agent)
        .add_edge(planner_agent, coordinator)
        .build()
    )

    user_request = "Quiero ir a algún lugar cálido el próximo mes"
    print(f"▶️  Iniciando planificador de viajes con: \"{user_request}\"\n")

    stream = workflow.run(user_request, stream=True)

    while True:
        pending: dict[str, str] = {}
        async for event in stream:
            if event.type == "request_info":
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n📍 Itinerario:\n{event.data}")

        if not pending:
            break

        for request_id, request in pending.items():
            print(f"\n⏸️  El agente pregunta: {request.message}")
            answer = input("💬 Tu respuesta: ")
            pending[request_id] = answer

        stream = workflow.run(stream=True, responses=pending)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
