import json
import os

import azure.identity
import openai
from dotenv import load_dotenv
from rich import print

# Configura el cliente para usar Azure OpenAI u OpenAI
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "azure")

if API_HOST == "azure":
    token_provider = azure.identity.get_bearer_token_provider(
        azure.identity.DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = openai.OpenAI(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
    )
    MODEL_NAME = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
else:
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-5.4")


def lookup_weather(city_name: str | None = None, zip_code: str | None = None) -> dict:
    """Consulta el clima para un nombre de ciudad o código postal dado."""
    print(f"Consultando el clima para {city_name or zip_code}...\n")
    return {
        "city_name": city_name,
        "zip_code": zip_code,
        "weather": "soleado",
        "temperature": 24,
    }


tools = [
    {
        "type": "function",
        "function": {
            "name": "lookup_weather",
            "description": "Consulta el clima para un nombre de ciudad o código postal dado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "El nombre de la ciudad",
                    },
                    "zip_code": {
                        "type": "string",
                        "description": "El código postal",
                    },
                },
                "strict": True,
                "additionalProperties": False,
            },
        },
    }
]

messages = [
    {"role": "system", "content": "Eres un chatbot del clima. Responde en español."},
    {"role": "user", "content": "¿Está soleado en Madrid?"},
]
response = client.chat.completions.create(
    model=MODEL_NAME,
    messages=messages,
    tools=tools,
    tool_choice="auto",
)


# Ahora ejecuta la función según lo indicado
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    function_name = tool_call.function.name
    function_arguments = json.loads(tool_call.function.arguments)
    print(function_name)
    print(function_arguments)

    if function_name == "lookup_weather":
        messages.append(response.choices[0].message)
        result = lookup_weather(**function_arguments)
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
        response = client.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools)
        print(f"Respuesta de {MODEL_NAME} en {API_HOST}:")
        print(response.choices[0].message.content)

else:
    print(response.choices[0].message.content)
