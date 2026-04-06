"""Workflow fan-out/fan-in con grupos de aristas explícitos.

Demuestra: WorkflowBuilder.add_fan_out_edges + add_fan_in_edges.
Un dispatcher envía un prompt a tres agentes expertos en paralelo, y luego
un agregador recibe todos los resultados como una lista y los consolida
en un solo reporte estructurado.

Ejecutar:
    uv run examples/spanish/workflow_fan_out_fan_in_edges.py
    uv run examples/spanish/workflow_fan_out_fan_in_edges.py --devui  (abre DevUI en http://localhost:8097)
"""

import asyncio
import os
import sys
from dataclasses import dataclass

from agent_framework import Agent, AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
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


class DispatchPrompt(Executor):
    """Emite el mismo prompt hacia abajo para que las aristas fan-out lo transmitan."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        """Envía un solo prompt a todas las ramas expertas downstream."""
        await ctx.send_message(prompt)


@dataclass
class AggregatedInsights:
    """Contenedor tipado para perspectivas consolidadas de expertos."""

    research: str
    marketing: str
    legal: str


class AggregateInsights(Executor):
    """Une las salidas de ramas fan-in y emite un reporte consolidado."""

    @handler
    async def aggregate(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, str],
    ) -> None:
        """Reduce una lista de respuestas expertas a un resumen estructurado."""
        expert_outputs: dict[str, str] = {"research": "", "marketing": "", "legal": ""}
        # Procesa result.executor_id y result.agent_response.text
        for result in results:
            executor_id = result.executor_id.lower()
            text = result.agent_response.text
            if "research" in executor_id:
                expert_outputs["research"] = text
            elif "market" in executor_id:
                expert_outputs["marketing"] = text
            elif "legal" in executor_id:
                expert_outputs["legal"] = text

        aggregated = AggregatedInsights(
            research=expert_outputs["research"],
            marketing=expert_outputs["marketing"],
            legal=expert_outputs["legal"],
        )

        consolidated = (
            "=== Brief de Lanzamiento Consolidado ===\n\n"
            f"Hallazgos de Investigación:\n{aggregated.research}\n\n"
            f"Enfoque de Marketing:\n{aggregated.marketing}\n\n"
            f"Notas Legales/Compliance:\n{aggregated.legal}\n"
        )
        await ctx.yield_output(consolidated)


dispatcher = DispatchPrompt(id="dispatcher")

researcher = Agent(
    client=client,
    name="Researcher",
    instructions=(
        "Eres un investigador de mercado experto. "
        "Dado el prompt, proporciona insights factuales concisos, oportunidades y riesgos. "
        "Usa viñetas cortas."
    ),
)

marketer = Agent(
    client=client,
    name="Marketer",
    instructions=(
        "Eres un estratega de marketing. "
        "Dado el prompt, propone una propuesta de valor clara y mensajes para la audiencia. "
        "Usa viñetas cortas."
    ),
)

legal = Agent(
    client=client,
    name="Legal",
    instructions=(
        "Eres un revisor legal y de compliance. "
        "Dado el prompt, lista restricciones, disclaimers y preocupaciones de políticas. "
        "Usa viñetas cortas."
    ),
)

aggregator = AggregateInsights(id="aggregator")

workflow = (
    WorkflowBuilder(
        name="FanOutFanInEdges",
        description="Explicit fan-out/fan-in using edge groups.",
        start_executor=dispatcher,
        output_executors=[aggregator],
    )
    .add_fan_out_edges(dispatcher, [researcher, marketer, legal])
    .add_fan_in_edges([researcher, marketer, legal], aggregator)
    .build()
)


async def main() -> None:
    """Ejecuta el ejemplo con un prompt e imprime la salida agregada."""
    prompt = "Vamos a lanzar una bicicleta eléctrica económica para commuters urbanos."
    print(f"Prompt: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8097, auto_open=True)
    else:
        asyncio.run(main())
