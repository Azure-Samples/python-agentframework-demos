"""Workflow interactivo de handoff con entrada de usuario human-in-the-loop.

Demuestra: HandoffBuilder sin modo autónomo — el workflow pausa para pedir
entrada del usuario entre turnos de agentes mediante eventos HandoffAgentUserRequest.

Un agente de triaje dirige problemas de clientes a agentes especialistas (seguimiento
de pedidos, devoluciones). Sin .with_autonomous_mode(), el framework pausa después de
cada respuesta del agente y espera a que el humano proporcione el siguiente mensaje.

Ejecutar:
    uv run examples/spanish/workflow_hitl_handoff.py
"""

import asyncio
import os
import sys
from typing import Annotated, Any

from agent_framework import Agent, AgentResponse, AgentResponseUpdate, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

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


# --- Herramientas ---


@tool
def process_return(
    order_number: Annotated[str, "The 3-digit order number"],
    return_type: Annotated[str, "Either 'refund' or 'replacement'"],
) -> str:
    """Procesa una devolución de producto para el pedido indicado."""
    return f"Devolución procesada para el pedido {order_number}: {return_type} aprobado. Correo de confirmación enviado."


# --- Agentes ---

triage_agent = Agent(
    client=client,
    name="triage_agent",
    instructions=(
        "Eres un agente de triaje de soporte al cliente. Saluda al cliente, entiende su problema "
        "y transfiere al especialista correcto: order_agent para consultas de pedidos, "
        "return_agent para devoluciones. No puedes manejar problemas específicos tú mismo — siempre transfiere. "
        "Si un especialista acaba de terminar de ayudar, pregunta al cliente si necesita algo más "
        "— NO reenvíes al mismo especialista. "
        "NO pidas información de contacto, correo electrónico ni número de teléfono. "
        "NO digas 'Adiós' hasta que el cliente confirme explícitamente que no tiene más preguntas."
    ),
)

order_agent = Agent(
    client=client,
    name="order_agent",
    instructions=(
        "Eres el especialista en seguimiento de pedidos. Ayuda al cliente a verificar el estado de su pedido. "
        "Cuando termines, transfiere de vuelta a triage_agent."
    ),
)

return_agent = Agent(
    client=client,
    name="return_agent",
    instructions=(
        "Eres el especialista en devoluciones. Ayuda al cliente a iniciar una devolución. "
        "Los únicos datos que necesitas son el número de pedido (3 dígitos) y si quieren un reembolso o reemplazo. "
        "Mantenlo simple y rápido. Una vez que el cliente confirme, llama a process_return para completar la devolución. "
        "Después de procesar la devolución, transfiere de vuelta a triage_agent."
    ),
    tools=[process_return],
)


# --- Principal ---


# --- Workflow ---

workflow = (
    HandoffBuilder(
        name="customer_support",
        participants=[triage_agent, order_agent, return_agent],
        termination_condition=lambda conversation: (
            len(conversation) > 0
            and any(word in conversation[-1].text.lower() for word in ("adiós", "adios", "chao"))
        ),
    )
    .with_start_agent(triage_agent)
    .build()
)


async def main() -> None:
    """Ejecuta un workflow interactivo de handoff con entrada del usuario."""
    initial_message = "Hola, necesito ayuda con un pedido."
    print(f"👤 Tú: {initial_message}\n")

    stream = workflow.run(initial_message, stream=True)

    while True:
        pending: list = []
        async for event in stream:
            if event.type == "request_info":
                pending.append(event)
            elif event.type == "handoff_sent":
                print(f"\n🔀 [Transferencia: {event.data.source} → {event.data.target}]")
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.text:
                        print(f"🤖 {msg.author_name or msg.role}: {msg.text}")
            elif event.type == "output" and not isinstance(event.data, (AgentResponseUpdate, AgentResponse)):
                if isinstance(event.data, list) and event.data:
                    last_msg = event.data[-1]
                    print(f"\n🤖 {last_msg.author_name or last_msg.role}: {last_msg.text}")
                print("\n✅ Conversación finalizada.")

        if not pending:
            break

        responses: dict[str, Any] = {}
        for request_event in pending:
            if isinstance(request_event.data, HandoffAgentUserRequest):
                # Muestra la respuesta del agente
                agent_response = request_event.data.agent_response
                for msg in agent_response.messages:
                    if msg.text:
                        print(f"🤖 {msg.author_name}: {msg.text}")

                # Obtiene la entrada del usuario
                user_input = input("\n👤 Tú: ").strip()
                if user_input.lower() in ("exit", "salir", "quit"):
                    responses[request_event.request_id] = HandoffAgentUserRequest.terminate()
                else:
                    responses[request_event.request_id] = HandoffAgentUserRequest.create_response(user_input)

        stream = workflow.run(responses=responses, stream=True)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8098, auto_open=True)
    else:
        asyncio.run(main())
