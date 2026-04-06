"""Fan-out/fan-in con agregación por voto mayoritario.

Tres agentes clasificadores usan distintas estrategias de razonamiento
(palabras clave, sentimiento, intención) para categorizar de forma
independiente un ticket de soporte. El agregador fan-in cuenta votos y
elige la etiqueta con mayoría.

Técnica de agregación: voto mayoritario (lógica pura, sin LLM en el agregador).

Nota: En producción, usar modelos distintos por rama fortalecería el
ensamble. Aquí simulamos diversidad con distintos estilos de prompting
sobre el mismo modelo.

Ejecutar:
    uv run examples/spanish/workflow_aggregator_voting.py
    uv run examples/spanish/workflow_aggregator_voting.py --devui  (abre DevUI en http://localhost:8103)
"""

import asyncio
import os
import sys
from collections import Counter
from enum import Enum

from agent_framework import Agent, AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
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


class Category(str, Enum):
    BUG = "bug"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"


class Classification(BaseModel):
    """Salida estructurada para cada agente clasificador."""

    category: Category


class DispatchPrompt(Executor):
    """Emite el texto del ticket hacia abajo para el broadcast de fan-out."""

    @handler
    async def dispatch(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(prompt)


class TallyVotes(Executor):
    """Agregador fan-in que cuenta votos y elige la etiqueta con mayoría."""

    @handler
    async def tally(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, str],
    ) -> None:
        """Cuenta votos de clasificadores y devuelve la categoría ganadora."""
        votes: list[tuple[str, str]] = []
        for result in results:
            classification = Classification.model_validate_json(result.agent_response.text)
            votes.append((result.executor_id, classification.category.value))

        labels = [label for _, label in votes]
        counter = Counter(labels)
        winner, count = counter.most_common(1)[0]

        report = f"  Resultado: {winner} ({count}/{len(votes)} votos)\n"
        for agent_id, label in votes:
            report += f"    {agent_id}: {label}\n"
        await ctx.yield_output(report)


dispatcher = DispatchPrompt(id="dispatcher")

keyword_classifier = Agent(
    client=client,
    name="ClasificadorPalabraClave",
    instructions=(
        "Clasifica el ticket de soporte en exactamente una categoría: bug, billing, feature_request o general.\n"
        "Reglas:\n"
        "- Si el mensaje menciona error, crash, bug, broken o fail → bug\n"
        "- Si el mensaje menciona invoice, charge, payment, refund o subscription → billing\n"
        "- Si el mensaje menciona add, wish, suggest, request o would be nice → feature_request\n"
        "- Si no, → general"
    ),
    default_options={"response_format": Classification},
)

sentiment_classifier = Agent(
    client=client,
    name="ClasificadorSentimiento",
    instructions=(
        "Clasifica el ticket de soporte en exactamente una categoría: bug, billing, feature_request o general.\n"
        "Analiza el tono emocional:\n"
        "- Frustrado o enojado porque algo no funciona → bug\n"
        "- Confundido o molesto por dinero/cargos → billing\n"
        "- Entusiasmado o esperanzado por capacidades nuevas → feature_request\n"
        "- Consulta informativa neutral → general"
    ),
    default_options={"response_format": Classification},
)

intent_classifier = Agent(
    client=client,
    name="ClasificadorIntencion",
    instructions=(
        "Clasifica el ticket de soporte en exactamente una categoría: bug, billing, feature_request o general.\n"
        "Enfócate en lo que el usuario quiere lograr:\n"
        "- Quiere que algo se arregle o repare → bug\n"
        "- Quiere reembolso, explicación de cargos o ajuste de cuenta → billing\n"
        "- Quiere una mejora o feature nueva → feature_request\n"
        "- Quiere información general o tiene una pregunta → general"
    ),
    default_options={"response_format": Classification},
)

tally = TallyVotes(id="tally")

workflow = (
    WorkflowBuilder(
        name="VotacionFanOutFanIn",
        description="Ensemble classification with majority-vote aggregation.",
        start_executor=dispatcher,
        output_executors=[tally],
    )
    .add_fan_out_edges(dispatcher, [keyword_classifier, sentiment_classifier, intent_classifier])
    .add_fan_in_edges([keyword_classifier, sentiment_classifier, intent_classifier], tally)
    .build()
)


async def main() -> None:
    """Ejecuta varios tickets de ejemplo y muestra el desglose de votos."""
    samples = [
        # Caso claro: los tres deberían coincidir
        "La app se crashea cada vez que intento subir una foto. Código de error 500.",
        # Keyword → feature_request (add, wish), Sentiment → bug (angry), Intent → bug (fix broken)
        "Ojalá el botón de exportar funcionara. Por favor agrega una solución — ¡pierdo datos a diario!",
        # Keyword → bug (error, fail), Sentiment → feature_request (hopeful), Intent → feature_request (new ability)
        "La búsqueda actual falla con consultas largas — estaría increíble si pudieras agregar fuzzy matching.",
    ]

    for sample in samples:
        print(f"Ticket: {sample}")
        events = await workflow.run(sample)
        for output in events.get_outputs():
            print(output)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    if "--devui" in sys.argv:
        from agent_framework.devui import serve

        serve(entities=[workflow], port=8103, auto_open=True)
    else:
        asyncio.run(main())
