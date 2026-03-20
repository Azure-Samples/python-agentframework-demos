# Python + Agents (Session 1): Building your first agent in Python

📺 [Watch the full recording on YouTube](https://www.youtube.com/watch?v=I4vCp9cpsiI) |
📑 [Download the slides (PPTX)](https://aka.ms/pythonagents/slides/building)

This write-up includes an annotated version of the presentation slides with timestamps to the video plus a summary of the live Q&A sessions.

## Table of contents

- [Session description](#session-description)
- [Annotated slides](#annotated-slides)
  - [Overview of the Python and Agents series](#overview-of-the-python-and-agents-series)
  - [Building your first agent in Python](#building-your-first-agent-in-python)
  - [Agenda: agents, tools, frameworks, MCP, middleware, and multi-agent](#agenda-agents-tools-frameworks-mcp-middleware-and-multi-agent)
  - [Following along with the GitHub repo and Codespaces](#following-along-with-the-github-repo-and-codespaces)
  - [What is an AI agent](#what-is-an-ai-agent)
  - [Python AI agent frameworks](#python-ai-agent-frameworks)
  - [What is tool calling](#what-is-tool-calling)
  - [Tool calling flow](#tool-calling-flow)
  - [Tell the LLM what functions it can call](#tell-the-llm-what-functions-it-can-call)
  - [Get function name and arguments from response](#get-function-name-and-arguments-from-response)
  - [Call a local function based on response](#call-a-local-function-based-on-response)
  - [Send tool results to LLM for final answer](#send-tool-results-to-llm-for-final-answer)
  - [Installing agent-framework](#installing-agent-framework)
  - [Single agent with a single tool](#single-agent-with-a-single-tool)
  - [Single agent with multiple tools](#single-agent-with-multiple-tools)
  - [Local experimentation with DevUI](#local-experimentation-with-devui)
  - [Model Context Protocol overview](#model-context-protocol-overview)
  - [MCP client and server architecture](#mcp-client-and-server-architecture)
  - [Agent with MCP server tools](#agent-with-mcp-server-tools)
  - [Agent with local MCP server](#agent-with-local-mcp-server)
  - [Agent with remote MCP server](#agent-with-remote-mcp-server)
  - [Agent middleware layers](#agent-middleware-layers)
  - [Agent middleware example](#agent-middleware-example)
  - [Chat middleware example](#chat-middleware-example)
  - [Function middleware example](#function-middleware-example)
  - [Class-based middleware](#class-based-middleware)
  - [Middleware with termination](#middleware-with-termination)
  - [Registering middleware per agent](#registering-middleware-per-agent)
  - [Registering middleware per run](#registering-middleware-per-run)
  - [Middleware scenarios](#middleware-scenarios)
  - [Supervisor agent with sub-agents](#supervisor-agent-with-sub-agents)
  - [Implementing a supervisor agent](#implementing-a-supervisor-agent)
  - [Multi-agent workflows preview](#multi-agent-workflows-preview)
  - [Next steps and resources](#next-steps-and-resources)
- [Live Chat Q&A](#live-chat-qa)
- [Discord Office Hours Q&A](#discord-office-hours-qa)

## Session description

This is the first session in the Python + Agents series, a six-session program covering how to build AI agents using the Microsoft Agent Framework. This session starts from the fundamentals — what an agent is, how tool calling works at the protocol level — and builds up to constructing agents with the `agent-framework` package. It covers single-agent patterns with one or multiple tools, MCP server integration (both local and remote), middleware for cross-cutting concerns like logging and content filtering, and a basic supervisor multi-agent architecture.

## Annotated slides

### Overview of the Python and Agents series

![Series overview slide listing all six sessions](images/slide_1.png)
[Watch from 00:00](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=0s)

The Python + Agents series spans six sessions across two weeks. Week one covers building a first agent, adding context and memory, and monitoring and evaluating agents. Week two covers AI-driven workflows, advanced multi-agent orchestration, and human-in-the-loop patterns. All sessions are recorded and available after the live stream. Registration is at [aka.ms/PythonAgents/series](https://aka.ms/PythonAgents/series).

### Building your first agent in Python

![Title slide for session 1](images/slide_2.png)
[Watch from 01:56](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=116s)

Session 1 is presented by Pamela Fox, a Python Cloud Advocate at Microsoft. The slides are available at [aka.ms/pythonagents/slides/building](https://aka.ms/pythonagents/slides/building).

### Agenda: agents, tools, frameworks, MCP, middleware, and multi-agent

![Agenda slide](images/slide_3.png)
[Watch from 03:16](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=196s)

The session covers six topics: what an agent is, how tool calling works, building agents with agent-framework, integrating agents with MCP server tools, agent middleware, and supervisor agent architecture. The first half focuses on understanding the low-level mechanics; the second half introduces higher-level abstractions.

### Following along with the GitHub repo and Codespaces

![Instructions for following along using Codespaces](images/slide_4.png)
[Watch from 04:25](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=265s)

A GitHub repository at [aka.ms/python-agentframework-demos](https://aka.ms/python-agentframework-demos) contains all demo code. To follow along, create a GitHub Codespace from the repo — the dev container is pre-configured with Python, `uv`, and all dependencies. The Codespace takes a few minutes to start up. A `.env` file with Azure OpenAI credentials needs to be configured (or an API key from another provider can be used instead).

### What is an AI agent

![Definition of an AI agent with diagram](images/slide_6.png)
[Watch from 07:24](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=444s)

An AI agent uses an LLM to run tools in a loop to achieve a goal. The key elements are the LLM (the reasoning engine), tools (functions the agent can call), and a loop (the agent keeps calling tools until the goal is met). Agents can be augmented with context (background knowledge), memory (recall of past interactions), planning (multi-step reasoning), and human oversight.

Without tools, an LLM can only generate text based on its training data. Tools let the agent take actions — calling APIs, querying databases, running computations — and incorporate live data into its responses. The loop is what distinguishes an agent from a simple tool-calling LLM: the agent iterates, using tool results to decide what to do next.

### Python AI agent frameworks

![Table of four Python AI agent frameworks](images/slide_7.png)
[Watch from 13:43](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=823s)

Four frameworks are highlighted. **agent-framework** is a Microsoft framework (successor to AutoGen and Semantic Kernel) with support for agentic patterns and Azure integrations. **LangChain v1** is an agent-centric framework built on LangGraph with optional LangSmith monitoring. **pydantic-ai** focuses on type safety and observability via Logfire/OpenTelemetry. **openai-agents** is OpenAI's framework optimized for OpenAI models and the Responses API.

This session uses agent-framework for all demos, but the concepts (tool calling, MCP, middleware, multi-agent patterns) apply across frameworks. The important thing is to understand the patterns, not to memorize a specific API.

### What is tool calling

![Explanation of tool calling with diagram](images/slide_9.png)
[Watch from 16:07](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=967s)

Tool calling (also called function calling) lets an LLM generate structured function calls instead of just text. The developer defines functions with JSON schemas describing parameters. When a user asks a question like "What's the weather in Paris?", the LLM responds with a function name (`get_weather`) and arguments (`"Paris"`) rather than trying to answer from training data. The developer's code then executes the actual function and feeds the result back to the LLM for a natural language response.

### Tool calling flow

![Five-step tool calling flow diagram](images/slide_10.png)
[Watch from 17:30](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1050s)

The tool calling flow has five steps: (1) code tells the LLM what tools are available, (2) the LLM responds with a suggested tool name and arguments, (3) code calls the local function, (4) code sends the return value back to the LLM along with prior messages, (5) the LLM generates a final response incorporating the tool result. This is the foundational mechanism that all agent frameworks build on.

### Tell the LLM what functions it can call

![Code example: defining tool JSON schema and calling the API](images/slide_11.png)
[Watch from 19:17](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1157s)

Tools are defined as JSON objects with a function name, description, and parameter schema. Each parameter has a type and description. This schema is passed to the OpenAI chat completions API via the `tools` parameter alongside the messages. The LLM uses the schema to understand what functions are available and what arguments they expect.

```python
tools = [{
  "type": "function",
  "function": {
    "name": "lookup_weather",
    "description": "Lookup the weather for a given city name or zip code.",
    "parameters": {
      "type": "object",
      "properties": {
        "city_name": {"type": "string", "description": "The city name"},
        "zip_code": {"type": "string", "description": "The zip code"}
      }
    }
  }
}]
```

### Get function name and arguments from response

![Code example: extracting function name and arguments](images/slide_12.png)
[Watch from 21:51](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1311s)

When the LLM decides to call a tool, the response includes `tool_calls` on the message object. Each tool call contains the function name and a JSON string of arguments that must be parsed with `json.loads()`. If there are no tool calls, the response is just regular text content.

### Call a local function based on response

![Code example: executing the local function](images/slide_13.png)
[Watch from 22:17](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1337s)

The developer is responsible for actually calling the function. The code matches the function name from the LLM response to a local Python function and unpacks the arguments with `**`. The LLM never executes code — it only suggests which function to call and with what arguments.

### Send tool results to LLM for final answer

![Code example: sending tool result back to LLM](images/slide_14.png)
[Watch from 23:06](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1386s)

After calling the function, the code appends the assistant's original message (with the tool call) and a new `tool` role message containing the JSON-serialized result. This full message history is sent back to the LLM in a second API call. The LLM then generates a natural language answer incorporating the tool result, e.g., "It's currently sunny in Los Angeles, CA with a temperature around 75°F."

This manual four-step process is exactly what agent frameworks automate. Understanding it helps debug issues when using higher-level abstractions.

### Installing agent-framework

![Installation instructions for agent-framework subpackages](images/slide_16.png)
[Watch from 24:27](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1467s)

Rather than installing the full `agent-framework` package, install only the subpackages needed: `agent-framework-core` for the core agent primitives and `agent-framework-devui` for the local development UI. This reduces indirect dependencies. The demo repository pins to a specific git commit since agent-framework was undergoing rapid changes at the time of the session.

### Single agent with a single tool

![Architecture diagram and code for single agent with one tool](images/slide_18.png)
[Watch from 27:20](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1640s)

The simplest agent pattern: one agent with one tool. Define a tool using the `@tool` decorator on a Python function with typed, annotated arguments and a docstring. The framework automatically generates the JSON schema from the type hints and descriptions. Create an `Agent` with a client, instructions (system prompt), and a list of tools. Call `agent.run()` with a user message.

```python
@tool
def get_weather(
    city: Annotated[str, Field(description="City name, spelled out fully")],
) -> dict:
    """Returns weather data, a dict with temperature and description."""
    return {"temperature": 72, "description": "Sunny"}

agent = Agent(client=client,
    instructions="You're an info agent. Answer questions cheerfully.",
    tools=[get_weather])
response = await agent.run("Whats weather today in San Francisco?")
```

The `@tool` decorator replaces all the manual JSON schema definition and function dispatch from the earlier examples. The framework handles the tool calling loop automatically — calling the function, sending results back to the LLM, and iterating until a final response is ready.

### Single agent with multiple tools

![Architecture diagram and code for agent with multiple tools](images/slide_20.png)
[Watch from 32:56](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=1976s)

When an agent has multiple tools, it must decide which tool to use and in what order. This example builds a weekend planner agent with three tools: `get_current_date`, `get_weather`, and `get_activities`. Given a question like "Plan my weekend in Portland," the agent first calls `get_current_date` to know what day it is, then calls `get_weather` for the forecast, and finally calls `get_activities` with the city and date. The LLM decides the call order based on parameter dependencies.

The agent may call tools in parallel if they don't depend on each other's outputs. It may also call tools multiple times — for example, calling `get_weather` for both Saturday and Sunday. The tool-calling loop continues until the agent has enough information to produce a final answer.

### Local experimentation with DevUI

![DevUI playground screenshot](images/slide_21.png)
[Watch from 38:33](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2313s)

DevUI is a local web-based playground for experimenting with agents. It provides a chat interface and shows full traces of tool calls, letting developers see exactly which tools were invoked, with what arguments, and what they returned. Start it with:

```python
from agent_framework.devui import serve
serve(entities=[agent], auto_open=True)
```

DevUI is useful for rapid iteration during development. It opens a browser window with a chat panel where developers can send messages and observe the agent's reasoning process in real time.

### Model Context Protocol overview

![MCP protocol overview](images/slide_23.png)
[Watch from 43:07](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2587s)

The Model Context Protocol (MCP) is an open protocol created by Anthropic that standardizes how LLMs interact with external tools, data sources, and applications. Instead of each framework implementing its own tool integration, MCP provides a common interface. An MCP server exposes tools, prompts, and resources that any MCP-compatible client can discover and use. See [modelcontextprotocol.io](https://modelcontextprotocol.io/) for the specification.

### MCP client and server architecture

![MCP architecture diagram with hosts, clients, and servers](images/slide_24.png)
[Watch from 43:30](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2610s)

An MCP host (such as VS Code, Claude Code, or a custom agent) contains one or more MCP clients. Each client connects to an MCP server. A server exposes tools, prompts, and resources. The host queries each server to discover available tools, then the agent can call those tools like any other tool. This decouples tool implementation from the agent framework.

### Agent with MCP server tools

![Architecture diagram: agent discovering and calling MCP tools](images/slide_25.png)
[Watch from 44:15](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2655s)

When an agent connects to MCP servers, it first sends a discovery request to each server asking "what tools do you have?" Each server responds with its tool list. The agent then has a combined pool of all available tools from all connected servers. When the LLM decides to call a tool, the framework routes the call to the correct MCP server. This is transparent — the agent treats MCP tools and local tools identically.

### Agent with local MCP server

![Code example: connecting to a local MCP server](images/slide_26.png)
[Watch from 45:26](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2726s)

To connect to a local MCP server, first start the server as a separate process (`uv run examples/mcp_server.py`), then create an `MCPStreamableHTTPTool` pointing to its URL. The MCP tool is passed to the agent just like a local tool. The demo shows an expense tracking server — when the user says "I bought a laptop today for $1200 on my visa," the agent calls the MCP server's expense-logging tool.

```python
async with (
    MCPStreamableHTTPTool(name="Local MCP Server",
        url="http://localhost:8000/mcp") as mcp_server,
    Agent(client=client, instructions="...", tools=[mcp_server]) as agent,
):
    response = await agent.run("I bought laptop today for $1200 on my visa.")
```

One consideration with MCP servers is token usage. Each discovered tool's schema is sent to the LLM as part of the prompt, which consumes tokens. Connecting to a server with many tools can significantly increase costs and reduce available context window.

### Agent with remote MCP server

![Code example: connecting to a remote MCP server](images/slide_27.png)
[Watch from 48:36](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=2916s)

Remote MCP servers work the same way as local ones — just point the URL to a remote endpoint. This example connects to the Microsoft Learn MCP server at `https://learn.microsoft.com/api/mcp`, which exposes documentation search tools. The agent can then answer questions like "How do I create an Azure Blob storage account using the az CLI?" by searching Microsoft's documentation through the MCP server.

### Agent middleware layers

![Diagram of three middleware layers: agent, chat, and function](images/slide_29.png)
[Watch from 50:21](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3021s)

Middleware intercepts agent execution at three different layers. **Agent middleware** wraps the entire agent run and receives an `AgentContext` with access to messages, metadata, and the ability to override results or terminate. **Chat middleware** wraps individual LLM calls and receives a `ChatContext` with access to chat options, messages, and the ability to modify or block responses. **Function middleware** wraps individual tool calls and receives a `FunctionInvocationContext` with the function name, arguments, and return value.

Each layer follows the same pattern: pre-process, call `call_next()` to continue the chain, then optionally post-process. Setting `terminate = True` on the context stops execution. Middleware executes in registration order — agent middleware runs first (outermost), then chat middleware, then function middleware (innermost).

### Agent middleware example

![Code example: timing agent middleware](images/slide_30.png)
[Watch from 51:40](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3100s)

An agent middleware function takes an `AgentContext` and a `call_next` callable. Code before `await call_next()` runs before the agent processes the request; code after runs when the agent completes. This timing middleware logs how long the entire agent execution takes.

```python
async def timing_agent_middleware(
    context: AgentContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    start = time.perf_counter()
    await call_next()
    elapsed = time.perf_counter() - start
    logger.info(f"Execution took {elapsed:.2f}s")
```

### Chat middleware example

![Code example: logging chat middleware](images/slide_31.png)
[Watch from 52:30](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3150s)

Chat middleware wraps each call to the LLM. The context provides access to the messages being sent, so middleware can log, modify, or filter them. This example logs the number of messages sent and confirms when a response is received.

### Function middleware example

![Code example: function invocation logging middleware](images/slide_32.png)
[Watch from 53:10](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3190s)

Function middleware wraps each tool call. Before `call_next()`, the context contains the function name and arguments. After `call_next()`, the context also contains the return value. This is useful for audit logging, input validation, and caching.

### Class-based middleware

![Code example: class-based chat middleware tracking message counts](images/slide_33.png)
[Watch from 53:50](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3230s)

Middleware can also be defined as a class that subclasses `ChatMiddleware` (or `AgentMiddleware` or `FunctionMiddleware`). This allows middleware to maintain state across invocations, such as counting the total number of messages processed. The class implements a `process()` method with the same signature as a function-based middleware.

### Middleware with termination

![Code example: blocking middleware that terminates on specific words](images/slide_34.png)
[Watch from 54:30](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3270s)

A middleware can completely stop agent execution by setting `context.terminate = True` and providing a result. This blocking middleware checks the last message for banned words (e.g., "nuclear") and returns a rejection message without ever calling the LLM. This pattern is useful for content filtering, authorization checks, and safety guardrails.

### Registering middleware per agent

![Code example: registering multiple middleware on an agent](images/slide_35.png)
[Watch from 55:26](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3326s)

Pass a list of middleware instances and functions to the `middleware` parameter when creating an agent. The list can mix function-based and class-based middleware, and can include middleware for all three layers (agent, chat, function). The framework sorts them by type automatically. In the demo, six different middleware are registered: timing, blocking, logging, counting, and more.

### Registering middleware per run

![Code example: adding middleware for a specific agent.run() call](images/slide_36.png)
[Watch from 56:45](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3405s)

Middleware can also be registered for a single invocation by passing it to `agent.run(middleware=[...])`. This is useful for adding temporary behavior like extra logging or debugging for a specific request without affecting other calls.

### Middleware scenarios

![Table of middleware use cases for each layer](images/slide_37.png)
[Watch from 57:20](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3440s)

Agent middleware is suited for logging, timing, content filtering, authorization, result caching, thread summarization, and dynamic system prompts. Chat middleware handles token tracking, latency measurement, budget enforcement, PII redaction, response moderation, and model fallback. Function middleware is ideal for audit logging, permission checks, input validation, caching, human-in-the-loop approval, tool call limits, and retry with backoff.

The key advantage of middleware is reusability. Once built, a middleware can be shared across agents within an organization. A centralized middleware repository could serve as a gallery of pre-built cross-cutting concerns.

### Supervisor agent with sub-agents

![Architecture diagram: supervisor routing to specialist agents](images/slide_39.png)
[Watch from 58:37](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3517s)

In a supervisor architecture, a parent agent decides which specialist sub-agents should handle a task. Each sub-agent has its own tools and instructions. The example is a parenting helper with two specialists: a weekend planning agent (with weather and activities tools) and a meal planning agent (with recipe and fridge-checking tools). The supervisor routes incoming requests to the appropriate specialist based on the query.

### Implementing a supervisor agent

![Code example: sub-agents wrapped as tool functions](images/slide_40.png)
[Watch from 59:14](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3554s)

The implementation is straightforward: create each sub-agent normally, then wrap each one in a `@tool`-decorated function. The supervisor agent lists these wrapper functions as its tools. When the supervisor decides to delegate, it calls the wrapper function, which runs the sub-agent and returns its text response.

```python
@tool
async def plan_weekend(query: str) -> str:
    response = await weekend_agent.run(query)
    return response.text

@tool
async def plan_meal(query: str) -> str:
    response = await meal_agent.run(query)
    return response.text

supervisor_agent = Agent(client=client,
    instructions="You're a supervisor managing a weekend planner & meal planner",
    tools=[plan_meal, plan_weekend])
```

This pattern works when tasks are clearly separable — the supervisor can unambiguously decide which sub-agent should handle a given request. For more complex orchestration involving conditional routing, parallel execution, or iterative collaboration, workflows (covered in week two) are more appropriate.

### Multi-agent workflows preview

![Diagram showing multi-agent workflow with conditional edges](images/slide_41.png)
[Watch from 01:00:44](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3644s)

For more complex multi-agent architectures, agent-framework supports workflows where agents are nodes in a graph. Workflows can include conditional edges, approval steps, human-in-the-loop checkpoints, and non-agent processing nodes. This is covered in detail in week two of the series.

### Next steps and resources

![Next steps slide with registration and resource links](images/slide_42.png)
[Watch from 01:01:02](https://www.youtube.com/watch?v=I4vCp9cpsiI&t=3662s)

Resources for continuing: the series registration at [aka.ms/PythonAgents/series](https://aka.ms/PythonAgents/series), past recordings and links at [aka.ms/pythonagents/resources](https://aka.ms/pythonagents/resources), and office hours in the Foundry Discord at [aka.ms/pythonai/oh](https://aka.ms/pythonai/oh) after each session. The next session covers adding context and memory to agents.


## Live Chat Q&A

### What model is used in the examples?

The primary model used is an Azure-deployed gpt-5-mini. For some examples, such as those with large token requirements, gpt-4.1-mini is used. GitHub models are also available but can have token limits impacting large tool schemas.

### How does the agent choose between multiple MCP servers exposing overlapping tools?

Agents rely on clear, specific tool names and descriptions to distinguish tools. When multiple servers have overlapping capabilities, system prompts can instruct the agent which server's tool to prefer. Proper MCP server design and prompt engineering help reduce ambiguity.

## Discord Office Hours Q&A

### How does middleware work in the Agent Framework?

📹 [0:01](https://youtube.com/watch?v=6HzauGnbRwA&t=1)

The Agent Framework supports three types of middleware, each operating at a different level:

- **Agent context middleware** — runs before and after `agent.run()`. You get access to the agent, messages, session (chat history), and options (e.g., whether streaming is enabled). You can override the result or modify options after the agent runs.
- **Function context middleware** — sits between the LLM calls and the tool/function calls. Useful for security-related concerns like permission checking, human-in-the-loop approvals, limiting the number of tool calls (e.g., cutting off a deep researcher after 12 tool calls), and tool retry logic.
- **Chat context middleware** — operates on the chat level, where you can override or filter the LLM's response (e.g., PII reduction).

All three middleware types let you mutate the result if needed. You can define middleware using simple functions or classes.

### Why do the tools in the demos have hard-coded return values?

📹 [4:01](https://youtube.com/watch?v=6HzauGnbRwA&t=241)

The demo tools return hard-coded values so they work without requiring API keys. For a real implementation, you'd replace the hard-coded returns with actual API calls (e.g., `requests.get()` to a weather API). Most weather APIs require keys, so the demos avoid that dependency.

### How does "context" differ across frameworks?

📹 [5:11](https://youtube.com/watch?v=6HzauGnbRwA&t=311)

The word "context" is extremely overloaded in the AI/agent space. In the Agent Framework specifically:

- **Context** (as in context providers) — information that always gets passed into the agent, as opposed to tools where definitions are passed but may or may not get called. This is covered more in the session on context and memory.
- **Middleware context** — the context object passed to middleware, giving it access to what it needs to operate (agent context, function context, chat context).

Every framework uses "context" differently, and even within a single framework it can mean different things depending on where it appears.

### What should I do if I get an "unavailable model" error with GPT-5 Mini?

📹 [6:52](https://youtube.com/watch?v=6HzauGnbRwA&t=412)

GPT-5 Mini access may be more restricted for some users on GitHub Models. Workarounds:

1. Check the [GitHub Marketplace models page](https://github.com/marketplace?type=models) to see if your account can access it
2. Create a `.env` file and set `GITHUB_MODEL` to a different model (e.g., `gpt-4o`)
3. Set the environment variable directly: `GITHUB_MODEL=gpt-4o`

All the examples in the repo check for a `GITHUB_MODEL` environment variable and fall back to a default. If deploying to Azure, GPT-5 Mini doesn't require an access request form and is available in many regions.

### Is it possible to see the full information sent to the LLM?

📹 [9:52](https://youtube.com/watch?v=6HzauGnbRwA&t=592)

Yes — set the logging level to debug:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This shows the full HTTP request being sent to the chat completions endpoint, including the JSON data with the conversation, model, streaming settings, and tool definitions. Since the Agent Framework wraps the OpenAI SDK, setting debug logging will show what's sent to the LLM.

Seeing the **response body** is harder — the repo's AGENTS.md file has tips for how to inspect response bodies with various SDKs. Open Telemetry tracing (covered in the Thursday session) provides another way to see this information.

### Were these examples hand-coded or vibe-coded?

📹 [13:54](https://youtube.com/watch?v=6HzauGnbRwA&t=834)

A mix. The earlier examples shown in the session were mostly hand-coded. For later, more complex examples, the process was collaborative with GitHub Copilot:

1. Use **plan mode** in GitHub Copilot
2. Provide an outline and point the agent to the most similar existing examples
3. Do a lot of back-and-forth on the plan before implementing
4. Let the agent generate the code based on the agreed-upon plan

It's described as a collaborative process rather than pure "vibe coding."

### Do you recommend starting with a deployed model (Azure Foundry) for learning agents?

📹 [15:53](https://youtube.com/watch?v=6HzauGnbRwA&t=953)

Yes, deploying sooner is better because:

- **GitHub Models rate limits** are reached quickly with agent workloads since agents use a lot of tokens
- **Local small models** generally aren't good enough for reliable tool calling (at least on typical developer machines)
- **Frontier models** (GPT-5 Mini, GPT-4o, etc.) provide the best tool calling support

Even $20 worth of credits goes a long way. You can use Azure, OpenAI directly, or both. The repo's README has instructions for deploying to Azure with `azd login` and `azd provision`.

### Can you use local Ollama models with the Agent Framework?

📹 [17:49](https://youtube.com/watch?v=6HzauGnbRwA&t=1069)

Yes, technically. The question is whether they work well. Tips:

- Use a model that **supports tool calling** — filter for "tools" on [ollama.com](https://ollama.com) models page
- Recommended models for tool calling: **Qwen 3**, **GPT-4All** (if your machine can run it), **GLM models** (if you have sufficient VRAM)
- When running locally, connect via `http://localhost:11434/v1`
- When running inside a **dev container**, use `http://host.docker.internal:11434/v1` instead

A live demo showed Llama 3.1 successfully handling a basic agent example through Ollama.

### Are all the models you're using free?

📹 [25:11](https://youtube.com/watch?v=6HzauGnbRwA&t=1511)

No. The cost breakdown:

- **GitHub Models** — free (used by default in Codespaces), but has rate limits
- **Azure** — not free, but used to avoid rate limits. Uses keyless connections with `DefaultAzureCredential`
- **OpenAI** — not free
- **Ollama** — free (runs on your local machine)

### Does the tracing in Agent Framework work with OpenAI tracing?

📹 [28:00](https://youtube.com/watch?v=6HzauGnbRwA&t=1680)

Probably not directly. Agent Framework uses **Open Telemetry** for tracing, while OpenAI tracing appears to be its own thing (built specifically for the OpenAI Agents SDK). Since the Agent Framework wraps the OpenAI client, there might theoretically be a way to pass tracing info through, but it would likely not work out of the box. This topic is covered more in the Thursday session on Open Telemetry.

### How does the supervisor agent pattern work?

📹 [29:06](https://youtube.com/watch?v=6HzauGnbRwA&t=1746)

A supervisor agent manages multiple specialist agents by wrapping them as tools:

1. The supervisor has instructions describing it manages specialist agents and should decide which to call
2. Each specialist agent is wrapped as a tool function — e.g., `plan_meal` is a tool that runs the meal agent with a query and returns its response
3. The supervisor can potentially call multiple specialist agents, even in parallel

Key observations from the live demo:

- **Parallel tool calling** can happen — OpenAI models support suggesting multiple tool calls in a single response by default
- If the agent doesn't have enough information, it may ask follow-up questions instead of completing the task. You need either a conversation loop or enough detail in the initial prompt.
- Sub-agents are also useful for **reducing the context window**, which will be covered in the session on context and memory.

### Can you use GitHub Copilot models with the Agent Framework?

📹 [36:53](https://youtube.com/watch?v=6HzauGnbRwA&t=2213)

Yes. The Agent Framework has a GitHub Copilot provider:

1. Install the additional package: `agent-framework-github-copilot`
2. Import `GitHubCopilotAgent` instead of the regular `Agent` class
3. The Copilot CLI must be **installed and logged in** in the current environment

It works by wrapping the Copilot CLI binary. In the live demo, it was tricky to get working inside a dev container (required installing the Copilot CLI and logging in within the container). Once set up, you just swap `Agent` with `GitHubCopilotAgent`.

The GitHub Copilot team considers their agent runtime to be among the best available. Note that the Copilot CLI's agentic loop is actually different from VS Code's Copilot agentic loop — they implement things differently despite sharing the product name.

Links shared:

- [Agent Framework GitHub Copilot samples](https://github.com/Azure-Samples/python-agentframework-demos)

### Do you always use Codespaces or only for demos?

📹 [42:20](https://youtube.com/watch?v=6HzauGnbRwA&t=2540)

Lately, more local development instead of Codespaces. The main reason is that `azd login` (Azure Developer CLI login) is harder in Codespaces with the current tenant setup. Working locally (still in a dev container) makes it easier to stay logged into Azure. Codespaces is still liked in general, but the Azure authentication friction has pushed more work to local dev.

### What is YOLO mode in Copilot?

📹 [50:39](https://youtube.com/watch?v=6HzauGnbRwA&t=3039)

YOLO mode auto-approves all tool/command executions without confirmation. It's available both in the **Copilot CLI** and **VS Code** (search for "auto approve" in settings).

Caution: Even inside dev containers and Codespaces, authenticated tools (like the GitHub MCP server) can still perform real actions. The recommendation is to approve commands **per session** (per chat thread) rather than enabling full YOLO mode globally, since authenticated access to services like GitHub means an agent could make real changes.