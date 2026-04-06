"""Workflow de chat simple con human-in-the-loop — patrón "siempre preguntar".

Demuestra: ctx.request_info(), @response_handler, y el bucle de eventos HITL
en la forma más simple posible. Sin salidas estructuradas, sin lógica de enrutamiento.

Un agente de chat responde al usuario, luego el executor siempre pausa para pedir
el siguiente mensaje. El humano puede escribir "done/salir" para terminar la conversación.
Este es el patrón HITL mínimo — cada respuesta del agente dispara un turno humano.

Ejecutar:
    uv run examples/spanish/workflow_hitl_requests.py
"""

import asyncio
import os
from dataclasses import dataclass

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

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

# Configura el cliente según el host de la API
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


# --- Dataclass de solicitud HITL ---


@dataclass
class UserPrompt:
    """Solicitud enviada al humano después de cada respuesta del agente."""

    message: str


# --- Executor que siempre pregunta al humano ---


class ChatCoordinator(Executor):
    """Después de cada respuesta del agente, pausa y pide entrada al humano."""

    def __init__(self, agent_id: str, id: str = "chat_coordinator"):
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def start(self, request: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Envía el primer mensaje del usuario al agente."""
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[request])], should_respond=True),
            target_id=self._agent_id,
        )

    @handler
    async def on_agent_response(self, result: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Siempre pausa y pide al humano el siguiente mensaje."""
        await ctx.request_info(
            request_data=UserPrompt(message=result.agent_response.text),
            response_type=str,
        )

    @response_handler
    async def on_human_reply(
        self,
        original_request: UserPrompt,
        reply: str,
        ctx: WorkflowContext[AgentExecutorRequest, str],
    ) -> None:
        """Reenvía la respuesta del humano al agente, o termina la conversación."""
        if reply.strip().lower() in ("done", "salir"):
            await ctx.yield_output("Conversación terminada.")
            return
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[reply])], should_respond=True),
            target_id=self._agent_id,
        )


# --- Principal ---


async def main() -> None:
    """Ejecuta el workflow de chat HITL simple."""
    chat_agent = Agent(
        name="ChatAgent",
        instructions="Eres un asistente amigable y servicial. Mantén las respuestas concisas (2-3 oraciones).",
        client=client,
    )

    coordinator = ChatCoordinator(agent_id="ChatAgent")

    workflow = (
        WorkflowBuilder(start_executor=coordinator)
        .add_edge(coordinator, chat_agent)
        .add_edge(chat_agent, coordinator)
        .build()
    )

    first_message = "¿Cuáles son algunas cosas divertidas para hacer en Ciudad de México?"
    print(f'▶️  Iniciando chat con: "{first_message}"')

    stream = workflow.run(first_message, stream=True)

    while True:
        pending: dict[str, str] = {}
        async for event in stream:
            if event.type == "request_info":
                pending[event.request_id] = event.data
            elif event.type == "output" and not isinstance(event.data, AgentResponseUpdate):
                print(f"\n{event.data}")

        if not pending:
            break

        for request_id, request in pending.items():
            print(f"\n🤖 Agente: {request.message}")
            reply = input("💬 Tú (o 'done/salir'): ")
            pending[request_id] = reply

        stream = workflow.run(stream=True, responses=pending)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
