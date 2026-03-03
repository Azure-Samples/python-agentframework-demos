# Instructions for coding agents

This repository contains many examples of using the Microsoft Agent Framework in Python (agent-framework), sometimes abbreviated as MAF.

The agent-framework GitHub repo is here:
https://github.com/microsoft/agent-framework
It contains both Python and .NET agent framework code, but we are only using the Python packages in this repo.

MAF is changing rapidly still, so we sometimes need to check the repo changelog and issues to see if there are any breaking changes that might affect our code. 
The Python changelog is here:
https://github.com/microsoft/agent-framework/blob/main/python/CHANGELOG.md

MAF documentation is available on Microsoft Learn here:
https://learn.microsoft.com/agent-framework/
When available, the MS Learn MCP server can be used to explore the documentation, ask questions, and get code examples.

## Package management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Use `uv` commands instead of `pip`:

```bash
uv add <package>
uv sync
```

## Spanish translations

There are Spanish equivalents of each example in /examples/spanish.

Each example .py file should have a corresponding file with the same name under /examples/spanish/ that is the translation of the original, but with the same code. Here's a guide on what should be translated vs. what should be left in English:

* Comments: Spanish
* Docstrings: Spanish
* System prompts (agent instructions): Spanish
* Identifiers (functions/classes/vars): English
* User-facing output/data (e.g., example responses, sample values): Spanish
* @tool function names: English
* @tool parameter descriptions (Field(description=...)): English
* @tool docstrings: Spanish
* HITL control words: bilingual (approve/aprobar, exit/salir)
* Agent and workflow names: English ("TravelPlannerAgent" should be the same in both versions, not "AgentePlanificadorDeViajes")

Use informal (tuteo) LATAM Spanish, tu not usted, puedes not podes, etc. The content is technical so if a word is best kept in English, then do so.

The /examples/spanish/README.md corresponds to the root README.md and should be kept in sync with it, but translated to Spanish.

## Debugging Azure Python SDK HTTP requests

When debugging HTTP interactions between Azure Python SDKs (like `azure-ai-evaluation`) and Azure services, there are three levels of logging you can enable:

### 1. Azure SDK logger (request headers and URLs)

Set the Azure SDK loggers to DEBUG level to see request URLs, headers, and status codes:

```python
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("azure").setLevel(logging.DEBUG)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.DEBUG)
```

### 2. Raw HTTP wire data (request/response headers)

Enable `http.client` debug logging to see the raw HTTP wire protocol, including request and response headers:

```python
import http.client
http.client.HTTPConnection.debuglevel = 1
```

Note: Response bodies will typically not be visible at this level because Azure SDKs use gzip compression, and `http.client` logs the raw compressed bytes.

### 3. Decompressed response bodies

To see actual response bodies, monkey-patch the Azure SDK's `HttpLoggingPolicy.on_response` method. This works because `response.http_response.body()` returns the decompressed content:

```python
from azure.core.pipeline.policies import HttpLoggingPolicy

_original_on_response = HttpLoggingPolicy.on_response

def _on_response_with_body(self, request, response):
    _original_on_response(self, request, response)
    try:
        body = response.http_response.body()
        if body:
            _logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
            _logger.debug("Response body: %s", body[:4096].decode("utf-8", errors="replace"))
    except Exception:
        pass

HttpLoggingPolicy.on_response = _on_response_with_body
```
