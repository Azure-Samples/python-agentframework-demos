import json
import os

import azure.identity
import openai
from dotenv import load_dotenv
from rich import print

# Configure OpenAI client based on environment
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
elif API_HOST == "ollama":
    client = openai.OpenAI(
        base_url=os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1"),
        api_key=os.environ.get("OLLAMA_API_KEY", "nokeyneeded"),
    )
    MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
else:
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-5.4")


def lookup_weather(city_name: str | None = None, zip_code: str | None = None) -> dict:
    """Lookup the weather for a given city name or zip code."""
    print(f"Looking up weather for {city_name or zip_code}...\n")
    return {
        "city_name": city_name,
        "zip_code": zip_code,
        "weather": "sunny",
        "temperature": 75,
    }


tools = [
    {
        "type": "function",
        "name": "lookup_weather",
        "description": "Lookup the weather for a given city name or zip code.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "city_name": {
                    "type": ["string", "null"],
                    "description": "The city name",
                },
                "zip_code": {
                    "type": ["string", "null"],
                    "description": "The zip code",
                },
            },
            "required": ["city_name", "zip_code"],
            "additionalProperties": False,
        },
    }
]

messages = [
    {"role": "system", "content": "You are a weather chatbot."},
    {"role": "user", "content": "is it sunny in LA, CA?"},
]
response = client.responses.create(
    model=MODEL_NAME,
    input=messages,
    tools=tools,
    tool_choice="auto",
    store=False,
)


# Now actually call the function as indicated
function_calls = [item for item in response.output if item.type == "function_call"]
if function_calls:
    tool_call = function_calls[0]
    function_name = tool_call.name
    function_arguments = json.loads(tool_call.arguments)
    print(function_name)
    print(function_arguments)

    if function_name == "lookup_weather":
        result = lookup_weather(**function_arguments)
        messages.extend(response.output)
        messages.append({"type": "function_call_output", "call_id": tool_call.call_id, "output": json.dumps(result)})
        response = client.responses.create(
            model=MODEL_NAME,
            input=messages,
            tools=tools,
            store=False,
        )
        print(f"Response from {MODEL_NAME} on {API_HOST}:")
        print(response.output_text)

else:
    print(response.output_text)
