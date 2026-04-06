"""Genera datos de evaluación para el agente planificador de viajes.

Ejecuta el agente con múltiples consultas de prueba y guarda los resultados en un
archivo JSONL que se puede usar con agent_evaluation_batch.py.

Uso:
    python agent_evaluation_generate.py
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from rich.logging import RichHandler
from rich.panel import Panel

handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

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


@tool
def get_weather(
    city: Annotated[str, Field(description="The city to get the weather forecast for.")],
    date_range: Annotated[str, Field(description="Date range in format 'YYYY-MM-DD to YYYY-MM-DD'.")],
) -> dict:
    """Devuelve el pronóstico del clima para una ciudad durante un rango de fechas."""
    logger.info(f"Obteniendo el clima para {city} ({date_range})")
    return {
        "city": city,
        "date_range": date_range,
        "forecast": [
            {"date": "Día 1", "high_f": 65, "low_f": 52, "conditions": "Parcialmente nublado"},
            {"date": "Día 2", "high_f": 70, "low_f": 55, "conditions": "Soleado"},
            {"date": "Día 3", "high_f": 62, "low_f": 50, "conditions": "Lluvia ligera"},
        ],
    }


@tool
def search_flights(
    origin: Annotated[str, Field(description="Departure city or airport code.")],
    destination: Annotated[str, Field(description="Arrival city or airport code.")],
    departure_date: Annotated[str, Field(description="Departure date in YYYY-MM-DD format.")],
    return_date: Annotated[str, Field(description="Return date in YYYY-MM-DD format.")],
) -> list[dict]:
    """Busca vuelos de ida y vuelta y devuelve opciones con precios."""
    logger.info(f"Buscando vuelos {origin} -> {destination} ({departure_date} a {return_date})")
    return [
        {"airline": "SkyAir", "price_usd": 850, "duration": "14h 20m", "stops": 1},
        {"airline": "OceanWings", "price_usd": 720, "duration": "16h 45m", "stops": 2},
        {"airline": "DirectJet", "price_usd": 1100, "duration": "12h 30m", "stops": 0},
    ]


@tool
def search_hotels(
    city: Annotated[str, Field(description="The city to search hotels in.")],
    checkin: Annotated[str, Field(description="Check-in date in YYYY-MM-DD format.")],
    checkout: Annotated[str, Field(description="Check-out date in YYYY-MM-DD format.")],
    max_price_per_night: Annotated[int, Field(description="Maximum price per night in USD.")],
) -> list[dict]:
    """Busca hoteles dentro de un presupuesto por noche y devuelve opciones con calificaciones."""
    logger.info(f"Buscando hoteles en {city} ({checkin} a {checkout}, máx ${max_price_per_night}/noche)")
    return [
        {"name": "Budget Inn Tokyo", "price_per_night_usd": 80, "rating": 3.8, "neighborhood": "Asakusa"},
        {"name": "Sakura Hotel", "price_per_night_usd": 120, "rating": 4.2, "neighborhood": "Shinjuku"},
        {"name": "Tokyo Garden Suites", "price_per_night_usd": 200, "rating": 4.6, "neighborhood": "Ginza"},
    ]


@tool
def get_activities(
    city: Annotated[str, Field(description="The city to find activities in.")],
    interests: Annotated[list[str], Field(description="List of interests, e.g. ['hiking', 'museums'].")],
) -> list[dict]:
    """Devuelve sugerencias de actividades para una ciudad según los intereses del usuario."""
    logger.info(f"Obteniendo actividades en {city} para intereses: {interests}")
    activities = []
    if "hiking" in [i.lower() for i in interests]:
        activities.extend(
            [
                {"name": "Excursión al Monte Takao", "cost_usd": 15, "duration": "4-5 horas"},
                {"name": "Caminata por Kamakura", "cost_usd": 25, "duration": "3 horas"},
            ]
        )
    if "museums" in [i.lower() for i in interests]:
        activities.extend(
            [
                {"name": "Museo Nacional de Tokio", "cost_usd": 10, "duration": "2-3 horas"},
                {"name": "teamLab Borderless", "cost_usd": 30, "duration": "2 horas"},
            ]
        )
    if not activities:
        activities = [{"name": "Tour a pie por la ciudad", "cost_usd": 0, "duration": "3 horas"}]
    return activities


@tool
def estimate_budget(
    total_budget: Annotated[int, Field(description="Total trip budget in USD.")],
    num_days: Annotated[int, Field(description="Number of days for the trip.")],
) -> dict:
    """Proporciona un desglose de presupuesto recomendado para vuelos, hoteles, actividades y comida."""
    logger.info(f"Estimando presupuesto: ${total_budget} para {num_days} días")
    flight_pct = 0.40
    hotel_pct = 0.30
    activities_pct = 0.15
    food_pct = 0.15
    return {
        "total_budget_usd": total_budget,
        "flights_usd": int(total_budget * flight_pct),
        "hotels_usd": int(total_budget * hotel_pct),
        "hotels_per_night_usd": int(total_budget * hotel_pct / num_days),
        "activities_usd": int(total_budget * activities_pct),
        "food_usd": int(total_budget * food_pct),
        "food_per_day_usd": int(total_budget * food_pct / num_days),
    }


tools = [get_weather, search_flights, search_hotels, get_activities, estimate_budget]

tool_definitions = [t.to_json_schema_spec()["function"] for t in tools]

AGENT_INSTRUCTIONS = (
    "Eres un asistente de planificación de viajes. Ayuda a los usuarios a planificar viajes "
    "consultando el clima, buscando vuelos y hoteles dentro del presupuesto, y sugiriendo "
    "actividades según sus intereses. Siempre proporciona un itinerario completo con costos "
    "para cada componente y asegúrate de que el total no exceda el presupuesto del usuario. "
    "Incluye información del clima para ayudar con el equipaje."
)

agent = Agent(
    client=client,
    instructions=AGENT_INSTRUCTIONS,
    tools=tools,
)

# Consultas de prueba y sus respuestas esperadas
TEST_CASES = [
    {
        "query": (
            "Planifica un viaje de 3 días de Nueva York (JFK) a Tokio, saliendo el 15 de marzo y "
            "regresando el 18 de marzo de 2026. Mi presupuesto es de $2000 en total. Me gusta el senderismo "
            "y los museos. Busca vuelos, hoteles de menos de $150/noche, consulta el clima y sugiere actividades."
        ),
        "ground_truth": (
            "Un itinerario completo de 3 días a Tokio desde Nueva York incluyendo: opciones de vuelos de ida y "
            "vuelta con precios, recomendaciones de hoteles dentro del presupuesto por noche, actividades de "
            "senderismo (ej. Monte Takao), visitas a museos (ej. Museo Nacional de Tokio, teamLab Borderless), "
            "pronóstico del clima para las fechas del viaje, un desglose completo de costos mostrando un total "
            "menor a $2000, y sugerencias de equipaje basadas en el clima."
        ),
    },
    {
        "query": (
            "Planifica un viaje de 5 días de San Francisco (SFO) a Tokio, saliendo el 1 de abril y "
            "regresando el 6 de abril de 2026. Mi presupuesto es de $3000 en total y me encantan los museos. "
            "Busca vuelos, hoteles de menos de $200/noche, consulta el clima y sugiere actividades en museos."
        ),
        "ground_truth": (
            "Un itinerario completo de 5 días a Tokio desde San Francisco incluyendo: opciones de vuelos de ida y "
            "vuelta con precios, recomendaciones de hoteles dentro del presupuesto por noche, sugerencias de "
            "actividades en museos (ej. Museo Nacional de Tokio, teamLab Borderless), pronóstico del clima para "
            "las fechas del viaje, un desglose completo de costos mostrando un total menor a $3000, y sugerencias "
            "de equipaje basadas en el clima."
        ),
    },
    {
        "query": (
            "Planifica un viaje de fin de semana de Los Ángeles (LAX) a Tokio, saliendo el viernes 20 de marzo "
            "y regresando el domingo 22 de marzo de 2026. Mi presupuesto es de $1500 en total. Me gusta el "
            "senderismo. Busca vuelos, hoteles de menos de $100/noche, consulta el clima y sugiere actividades de senderismo."
        ),
        "ground_truth": (
            "Un itinerario completo de 2 días a Tokio desde Los Ángeles incluyendo: opciones de vuelos de ida y "
            "vuelta con precios, recomendaciones de hoteles dentro del presupuesto por noche, sugerencias de "
            "actividades de senderismo (ej. Monte Takao, Caminata por Kamakura), pronóstico del clima para las "
            "fechas del viaje, un desglose completo de costos mostrando un total menor a $1500, y sugerencias "
            "de equipaje basadas en el clima."
        ),
    },
]


def convert_to_evaluator_messages(messages) -> list[dict]:
    """Convierte ChatMessages del agent framework al esquema de mensajes de Azure AI Evaluation."""
    evaluator_messages = []
    for msg in messages:
        role = str(msg.role.value) if hasattr(msg.role, "value") else str(msg.role)
        content_items = []
        for c in msg.contents:
            if c.type == "function_call":
                content_items.append(
                    {
                        "type": "tool_call",
                        "tool_call_id": c.call_id,
                        "name": c.name,
                        "arguments": json.loads(c.arguments) if isinstance(c.arguments, str) else c.arguments,
                    }
                )
            elif c.type == "function_result":
                if c.call_id:
                    if content_items:
                        evaluator_messages.append({"role": role, "content": content_items})
                        content_items = []
                    evaluator_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": c.call_id,
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_result": c.result,
                                }
                            ],
                        }
                    )
                    continue
                content_items.append(
                    {
                        "type": "tool_result",
                        "tool_result": c.result,
                    }
                )
            elif c.type == "text" and c.text:
                content_items.append({"type": "text", "text": c.text})
        if content_items:
            evaluator_messages.append({"role": role, "content": content_items})
    return evaluator_messages


async def main():
    output_file = Path(__file__).parent / "eval_data.jsonl"

    logger.info(f"Generando datos de evaluación para {len(TEST_CASES)} casos de prueba...")

    with open(output_file, "w", encoding="utf-8") as f:
        for i, test_case in enumerate(TEST_CASES):
            query = test_case["query"]
            logger.info(f"[{i + 1}/{len(TEST_CASES)}] Ejecutando agente: {query[:60]}...")

            response = await agent.run(query)
            print(Panel(response.text, title=f"Respuesta {i + 1}", border_style="blue"))

            eval_query = [
                {"role": "system", "content": AGENT_INSTRUCTIONS},
                {"role": "user", "content": [{"type": "text", "text": query}]},
            ]

            eval_data_row = {
                "query": eval_query,
                "response": convert_to_evaluator_messages(response.messages),
                "response_text": response.text,
                "ground_truth": test_case["ground_truth"],
                "tool_definitions": tool_definitions,
            }
            f.write(json.dumps(eval_data_row) + "\n")

    logger.info(f"Datos de evaluación guardados en {output_file}")
    logger.info(f"Ejecuta la evaluación por lotes con: python agent_evaluation_batch.py {output_file}")

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
