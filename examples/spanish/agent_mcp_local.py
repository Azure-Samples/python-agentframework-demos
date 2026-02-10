import asyncio
import logging
import os
from datetime import datetime

from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich import print
from rich.logging import RichHandler

# Configura logging
handler = RichHandler(show_path=False, rich_tracebacks=True, show_level=False)
logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configura el cliente para usar Azure OpenAI, GitHub Models u OpenAI
load_dotenv(override=True)
API_HOST = os.getenv("API_HOST", "github")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/")

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
        api_key=os.environ["OPENAI_API_KEY"],
        model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
    )


async def main() -> None:
    """Ejecuta un agente conectado a un servidor MCP local para registrar gastos."""
    async with (
        MCPStreamableHTTPTool(name="Expenses MCP Server", url=MCP_SERVER_URL) as mcp_server,
        ChatAgent(
            chat_client=client,
            instructions=(
                "Ayudas a la gente con tareas usando las herramientas disponibles. "
                f"La fecha de hoy es {datetime.now().strftime('%Y-%m-%d')}. "
            ),
            tools=[mcp_server],
        ) as agent,
    ):
        response = await agent.run("ayer compré una laptop por $1200 con mi visa.")
        print(response.text)

    if async_credential:
        await async_credential.close()


if __name__ == "__main__":
    asyncio.run(main())
