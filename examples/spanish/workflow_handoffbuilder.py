"""Orquestación de handoff en modo autónomo usando HandoffBuilder.

Demuestra: HandoffBuilder con .with_autonomous_mode() donde los agentes
se transfieren el control entre sí sin interacción human-in-the-loop.
Un agente de triage decide qué especialista involucrar primero; luego los
agentes hacen handoff libremente — el investigador reúne hechos, el writer
redacta contenido y el editor revisa (devolviendo al writer si se necesitan
revisiones).

Por defecto, cada participante puede hacer handoff a cualquier otro;
no se necesitan reglas explícitas de ruteo.

Referencia:
    https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff?pivots=programming-language-python#autonomous-mode

Ejecutar:
    uv run examples/spanish/workflow_handoffbuilder.py
"""

import asyncio
import logging
import os

from agent_framework import Agent, AgentResponseUpdate, MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console

logging.basicConfig(level=logging.WARNING)
console = Console()

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
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"], model=os.environ.get("OPENAI_MODEL", "gpt-5.4")
    )


async def main() -> None:
    # ── Herramienta MCP para el investigador ─────────────────────────────
    async with MCPStreamableHTTPTool(
        name="Microsoft Learn MCP",
        url="https://learn.microsoft.com/api/mcp",
    ) as mcp_server:
        # ── Agentes ──────────────────────────────────────────────────────

        triage = Agent(
            client=client,
            name="Triaje",
            instructions=(
                "Eres un coordinador de triaje para un equipo de creación de contenido. "
                "Analiza la solicitud del usuario y haz handoff al agente más adecuado: "
                "'Investigador' para investigación (paso inicial preferido para la mayoría de solicitudes), "
                "'Escritor' para redacción o 'Editor' para revisión. "
                "NO produzcas contenido tú — solo decide quién debe empezar y haz handoff."
            ),
        )

        researcher = Agent(
            client=client,
            name="Investigador",
            instructions=(
                "Eres un investigador. Usa la herramienta de búsqueda de Microsoft Learn para encontrar "
                "documentación relevante y actualizada sobre el tema. "
                "El paquete Microsoft Agent Framework para Python está documentado en "
                "learn.microsoft.com/agent-framework — busca términos como "
                "'agent framework workflow', 'agent framework orchestrations', etc. "
                "NO lo confundas con Microsoft Bot Framework — son productos distintos. "
                "Produce 3-5 viñetas concisas resumiendo tus hallazgos. "
                "Al terminar, haz handoff al Escritor."
            ),
            tools=[mcp_server],
        )

        writer = Agent(
            client=client,
            name="Escritor",
            instructions=(
                "Eres un escritor de redes sociales especializado en LinkedIn. "
                "Toma las viñetas del investigador y escribe un post de LinkedIn con gancho "
                "(80-120 palabras). Usa una apertura tipo hook, párrafos cortos y un CTA claro. "
                "Incluye 2-3 hashtags relevantes al final. Al terminar, haz handoff al Editor."
            ),
        )

        editor = Agent(
            client=client,
            name="Editor",
            instructions=(
                "Eres un editor de LinkedIn. Revisa el borrador del Escritor por claridad, tono y engagement. "
                "Si ves problemas (hook débil, relleno, CTA vago, formato pobre), "
                "da 2-3 críticas específicas y haz handoff al Escritor para revisión. "
                "Si el borrador está sólido o ya fue revisado, entrega la versión pulida "
                "con el prefijo 'FINAL:' en la primera línea. "
                "Cada respuesta DEBE O hacer handoff O entregar FINAL — nunca ambas."
            ),
        )

        # ── Construye el workflow de handoff (autónomo — sin interacción) ─

        workflow = (
            HandoffBuilder(
                name="content_pipeline",
                participants=[triage, researcher, writer, editor],
                termination_condition=lambda conversation: (
                    len(conversation) > 0 and conversation[-1].text.strip().startswith("FINAL:")
                ),
            )
            .with_start_agent(triage)
            .with_autonomous_mode()
            .build()
        )

        # ── Ejecuta ──────────────────────────────────────────────────────

        prompt = "Escribe un post de LinkedIn sobre desplegar agentes Python en Azure Container Apps."
        console.print(f"[bold]Prompt:[/bold] {prompt}\n")

        current_agent = None

        async for event in workflow.run(prompt, stream=True):
            if event.type == "handoff_sent":
                console.print(f"\n🔀 [bold yellow]Handoff:[/bold yellow] {event.data.source} → {event.data.target}\n")

            elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                if event.executor_id != current_agent:
                    current_agent = event.executor_id
                    console.print(f"\n🤖 [bold cyan]{current_agent}[/bold cyan]")
                console.print(event.data.text, end="")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
