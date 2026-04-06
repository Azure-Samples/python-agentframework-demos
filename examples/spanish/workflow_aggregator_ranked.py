"""Fan-out/fan-in con agregación de ranking usando LLM como juez.

Tres agentes creativos con diferentes personalidades (audaz, minimalista,
emocional) proponen cada uno un eslogan de marketing. Un ejecutor ranker
recopila las opciones, las formatea y usa un agente juez interno para
calificarlas y ordenarlas — dejando que el LLM evalúe creatividad,
memorabilidad y encaje con la marca.

Técnica de agregación: LLM como juez (generar N candidatos y rankear el mejor).

Ejecutar:
    uv run examples/spanish/workflow_aggregator_ranked.py
    uv run examples/spanish/workflow_aggregator_ranked.py --devui  (abre DevUI en http://localhost:8104)
"""

import asyncio
import os
import sys

from agent_framework import Agent, AgentExecutorResponse, Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import BaseModel, Field
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


class RankedSlogan(BaseModel):
    """Una sola entrada de eslogan rankeada."""

    rank: int = Field(description="Rank position, 1 = best.")
    agent_name: str = Field(description="Name of the agent that produced the slogan.")
    slogan: str = Field(description="The marketing slogan text.")
    score: int = Field(description="Score from 1 to 10.")
    justification: str = Field(description="One-sentence justification for the score.")


class RankedSlogans(BaseModel):
    """Salida tipada: una lista de eslóganes rankeados."""

    rankings: list[RankedSlogan] = Field(description="Slogans ranked from best to worst.")


class DispatchPrompt(Executor):
    """Emite el brief del producto hacia abajo para el broadcast de fan-out."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class RankerExecutor(Executor):
    """Agregador fan-in que formatea eslóganes candidatos y los rankea vía el cliente LLM."""

    def __init__(self, *, client: OpenAIChatClient, id: str = "Ranker") -> None:
        super().__init__(id=id)
        self._client = client

    @handler
    async def run(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, RankedSlogans],
    ) -> None:
        """Recopila eslóganes, los formatea y le pide al LLM que los rankee."""
        lines = []
        for result in results:
            slogan = result.agent_response.text.strip().strip("\"'").split("\n")[0].strip().strip("\"'")
            lines.append(f'- [{result.executor_id}]: "{slogan}"')

        messages = [
            Message(
                role="system",
                contents=[
                    (
                        "Eres un director creativo senior evaluando eslóganes de marketing. "
                        "Dada una lista de eslóganes candidatos, ordénalos del mejor al peor. "
                        "Para cada eslogan, da una puntuación de 1 a 10 y una justificación de una sola oración "
                        "evaluando creatividad, memorabilidad, claridad y encaje con la marca."
                    )
                ],
            ),
            Message(role="user", contents=["Eslóganes candidatos:\n" + "\n".join(lines)]),
        ]
        response = await self._client.get_response(messages, options={"response_format": RankedSlogans})
        await ctx.yield_output(response.value)


dispatcher = DispatchPrompt(id="dispatcher")

bold_writer = Agent(
    client=client,
    name="EscritorAudaz",
    instructions=(
        "Eres un copywriter audaz y dramático. "
        "Dado el brief del producto, propone UN eslogan de marketing contundente (máx. 10 palabras). "
        "Hazlo llamativo y con mucha confianza. Responde SOLO con el eslogan."
    ),
)

minimalist_writer = Agent(
    client=client,
    name="EscritorMinimalista",
    instructions=(
        "Eres un copywriter minimalista que valora la brevedad por encima de todo. "
        "Dado el brief del producto, propone UN eslogan de marketing ultra-corto (máx. 6 palabras). "
        "Menos es más. Responde SOLO con el eslogan."
    ),
)

emotional_writer = Agent(
    client=client,
    name="EscritorEmocional",
    instructions=(
        "Eres un copywriter con enfoque empático. "
        "Dado el brief del producto, propone UN eslogan de marketing (máx. 10 palabras) "
        "que conecte emocionalmente con la audiencia. Responde SOLO con el eslogan."
    ),
)

# El ejecutor ranker llama directamente al cliente LLM para manejar el fan-in —
# formatea los eslóganes recopilados y hace que el LLM los rankee.
ranker = RankerExecutor(client=client)

workflow = (
    WorkflowBuilder(
        name="RankingFanOutFanIn",
        description="Generate slogans in parallel, then LLM-judge ranks them.",
        start_executor=dispatcher,
        output_executors=[ranker],
    )
    .add_fan_out_edges(dispatcher, [bold_writer, minimalist_writer, emotional_writer])
    .add_fan_in_edges([bold_writer, minimalist_writer, emotional_writer], ranker)
    .build()
)


async def main() -> None:
    """Ejecuta el pipeline de eslóganes e imprime los resultados rankeados."""
    prompt = "Bicicleta eléctrica económica para commuters urbanos. Confiable, accesible y verde."
    print(f"Brief del producto: {prompt}\n")

    events = await workflow.run(prompt)
    for output in events.get_outputs():
        for entry in output.rankings:
            print(f'#{entry.rank} (puntaje {entry.score}) [{entry.agent_name}]: "{entry.slogan}"')
            print(f"   {entry.justification}\n")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8104, auto_open=True)
    else:
        asyncio.run(main())
