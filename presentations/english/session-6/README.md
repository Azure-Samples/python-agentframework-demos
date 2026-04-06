# Python + Agents (Session 6): Adding a human in the loop to workflows

📺 [Watch the full recording on YouTube](https://www.youtube.com/watch?v=7pGqASn-LEY) |
📑 [Download the slides (PDF)](https://aka.ms/pythonagents/slides/hitl)

This write-up includes an annotated version of the presentation slides with timestamps to the video plus a summary of the live Q&A sessions.

## Table of contents

- [Session description](#session-description)
- [Annotated slides](#annotated-slides)
  - [Overview of the Python and Agents series](#overview-of-the-python-and-agents-series)
  - [Adding a human in the loop to workflows](#adding-a-human-in-the-loop-to-workflows)
  - [Agenda: human-in-the-loop patterns](#agenda-human-in-the-loop-patterns)
  - [Following along with the GitHub repo and Codespaces](#following-along-with-the-github-repo-and-codespaces)
  - [Recap: what is an agentic workflow](#recap-what-is-an-agentic-workflow)
  - [Human-in-the-loop concept](#human-in-the-loop-concept)
  - [Why add a human in the loop](#why-add-a-human-in-the-loop)
  - [Reasons for adding HITL](#reasons-for-adding-hitl)
  - [HITL patterns in agent-framework](#hitl-patterns-in-agent-framework)
  - [Tool approval](#tool-approval)
  - [When do we need tool approval](#when-do-we-need-tool-approval)
  - [Defining tools that require approval](#defining-tools-that-require-approval)
  - [Handling tool approval in the event loop](#handling-tool-approval-in-the-event-loop)
  - [Requests and responses](#requests-and-responses)
  - [Requests and responses in workflows](#requests-and-responses-in-workflows)
  - [Simple chat with HITL: workflow topology](#simple-chat-with-hitl-workflow-topology)
  - [Executor code for handling requests and responses](#executor-code-for-handling-requests-and-responses)
  - [App code for handling requests and responses](#app-code-for-handling-requests-and-responses)
  - [HITL with structured outputs: workflow topology](#hitl-with-structured-outputs-workflow-topology)
  - [Agent definition with structured outputs](#agent-definition-with-structured-outputs)
  - [Executor code for handling structured response](#executor-code-for-handling-structured-response)
  - [Checkpoints and resuming](#checkpoints-and-resuming)
  - [The need for checkpoints in HITL workflows](#the-need-for-checkpoints-in-hitl-workflows)
  - [Workflow lifecycle with checkpoints](#workflow-lifecycle-with-checkpoints)
  - [Configuring checkpoint storage for workflows](#configuring-checkpoint-storage-for-workflows)
  - [Resuming a workflow from checkpoint](#resuming-a-workflow-from-checkpoint)
  - [Saving and restoring executor state](#saving-and-restoring-executor-state)
  - [Designing your custom checkpoint storage](#designing-your-custom-checkpoint-storage)
  - [Custom checkpoint storage design considerations](#custom-checkpoint-storage-design-considerations)
  - [Custom checkpoint storage with PostgreSQL](#custom-checkpoint-storage-with-postgresql)
  - [Handoff orchestration with HITL](#handoff-orchestration-with-hitl)
  - [Review: handoff orchestration](#review-handoff-orchestration)
  - [Configuring HandoffBuilder for interactivity](#configuring-handoffbuilder-for-interactivity)
  - [Handling HITL requests in HandoffBuilder](#handling-hitl-requests-in-handoffbuilder)
  - [End-to-end application](#end-to-end-application)
  - [Agentic banking assistant](#agentic-banking-assistant)
  - [Agents and MCP servers architecture](#agents-and-mcp-servers-architecture)
  - [Handoff workflow with checkpointing](#handoff-workflow-with-checkpointing)
  - [Next steps and resources](#next-steps-and-resources)
- [Discord Office Hours Q&A](#discord-office-hours-qa)

## Session description

In the final session of the Python + Agents series, we explored how to incorporate human-in-the-loop (HITL) interactions into agentic workflows using the Microsoft Agent Framework. The session focused on adding points where a workflow can pause, request input or approval from a user, and then resume once the human has responded.

We began with tool approval, which lets you gate sensitive operations so that an agent's proposed tool calls must be explicitly approved or rejected before execution. We then moved to the framework's requests-and-responses model, which provides a structured way for workflow executors to ask questions, collect human input, and continue execution with that data. We showed both a free-text approach and a structured-output approach that uses Pydantic models to drive the decision of when to request human input.

Next, we covered checkpoints and resuming, which allow workflows to pause and be restarted later — especially important for HITL scenarios where the human may not be available immediately. We walked through file-based checkpoint storage and then implemented a custom PostgreSQL checkpoint storage class.

We concluded with the handoff orchestration pattern in interactive mode, where agents dynamically route to each other and request user input between handoffs. A full-stack banking assistant demo brought together handoff, tool approval, checkpoints, and multiple agents backed by MCP servers — deployed on Azure with Document Intelligence for invoice scanning.

## Annotated slides

### Overview of the Python and Agents series

![Series overview slide](images/slide_1.png)
[Watch from 00:51](https://www.youtube.com/watch?v=7pGqASn-LEY&t=51s)

This is a six-part live stream series on building AI agents with the Microsoft Agent Framework. Session 6 is the final session, covering human-in-the-loop. Week one covered building individual agents, adding context and memory, and monitoring and evaluation. Week two covered workflows, advanced multi-agent orchestration, and now HITL. All sessions are recorded and available along with slides, code, and annotated writeups. Registration and resources are at [aka.ms/PythonAgents/series](https://aka.ms/PythonAgents/series).

### Adding a human in the loop to workflows

![Session title slide](images/slide_2.png)
[Watch from 01:26](https://www.youtube.com/watch?v=7pGqASn-LEY&t=86s)

This session covers adding human-in-the-loop patterns to both agents and workflows in Python using the Microsoft Agent Framework. Slides are available at [aka.ms/pythonagents/slides/hitl](https://aka.ms/pythonagents/slides/hitl).

### Agenda: human-in-the-loop patterns

![Agenda slide](images/slide_3.png)
[Watch from 01:49](https://www.youtube.com/watch?v=7pGqASn-LEY&t=109s)

The agenda covers why HITL matters for agents and workflows, tool approval for gating sensitive operations, requests and responses for structured human interaction, checkpoints and resuming for durable HITL workflows, handoff with HITL for interactive multi-agent routing, and an end-to-end application combining all these patterns.

### Following along with the GitHub repo and Codespaces

![Instructions for following along](images/slide_4.png)
[Watch from 02:13](https://www.youtube.com/watch?v=7pGqASn-LEY&t=133s)

All code is in the same GitHub repository used throughout the series at [aka.ms/python-agentframework-demos](https://aka.ms/python-agentframework-demos). Clicking the green "Code" button and selecting "Create codespace on main" opens a preconfigured VS Code environment in the browser with Python, UV, and all dependencies installed. The Codespace uses GitHub Models by default, which are free models available with a GitHub account up to a certain rate limit. All of today's examples should fit within that free tier. Running `git pull` is recommended to get the latest changes.

### Recap: what is an agentic workflow

![Agentic workflow recap](images/slide_5.png)
[Watch from 03:17](https://www.youtube.com/watch?v=7pGqASn-LEY&t=197s)

An agentic workflow is a flow that involves an agent at some point, typically for decision making or information synthesis. In agent-framework, a workflow is a graph with Executor nodes and edges between them. Many executor nodes can be agents, but they can also be custom nodes that do any sort of processing or data lookup.

### Human-in-the-loop concept

![Human-in-the-loop diagram](images/slide_6.png)
[Watch from 04:05](https://www.youtube.com/watch?v=7pGqASn-LEY&t=245s)

When an agent wants to take an action — sending an email, posting a comment, making a report — that action has real consequences. If there is not 100% confidence in the agent's decision, a human should review it first. Agents are given tools that perform write operations, and those operations can go wrong. A notable example: the OpenClaw agent, given full access to email and operating system, deleted half a user's inbox emails when that was never the intended task. If an agent can perform destructive or sensitive operations, humans should be in the approval loop.

### Why add a human in the loop

![Section divider: Why HITL?](images/slide_7.png)
[Watch from 06:29](https://www.youtube.com/watch?v=7pGqASn-LEY&t=389s)

This section covers the motivations for adding human checkpoints to agent workflows.

### Reasons for adding HITL

![Reasons for HITL](images/slide_8.png)
[Watch from 06:29](https://www.youtube.com/watch?v=7pGqASn-LEY&t=389s)

LLMs can produce uncertain, inconsistent, or incorrect outputs. Human checkpoints provide: **accuracy** (verify factual correctness before acting), **safety** (gate sensitive operations like refunds, emails, and deployments), **trust** (users see what the system will do before it acts, increasing confidence in the application), **compliance** (audit trail of human approvals for regulated workflows), and **control** (humans can redirect, refine, or halt a workflow at any point).

### HITL patterns in agent-framework

![HITL patterns overview](images/slide_9.png)
[Watch from 07:43](https://www.youtube.com/watch?v=7pGqASn-LEY&t=463s)

The Microsoft Agent Framework provides four HITL patterns. **Tool approval** requires sensitive tool calls to be approved before execution. **Requests and responses** let a workflow ask for human input (answers, choices, feedback) and continue once provided. **Checkpoints and resuming** support long-running tasks where the human may not be immediately available. **Handoff with HITL** enables dynamic multi-agent routing with interactive user input between handoffs.

### Tool approval

![Tool approval section](images/slide_10.png)
[Watch from 08:08](https://www.youtube.com/watch?v=7pGqASn-LEY&t=488s)

Tool approval is documented at [learn.microsoft.com/agent-framework/agents/tools/tool-approval](https://learn.microsoft.com/agent-framework/agents/tools/tool-approval).

### When do we need tool approval

![Tool approval comparison](images/slide_11.png)
[Watch from 08:13](https://www.youtube.com/watch?v=7pGqASn-LEY&t=493s)

Without tool approval, an agent decides to send an email and the tool executes automatically — the email gets sent even if it is wrong. With tool approval, the agent wants to send an email, the workflow pauses, the human reviews the proposed action, and the tool only executes if approved. Tool approval should be considered for financial operations (refunds, purchases), communications (emails, messages), destructive operations (deletions, deployments), and any irreversible action.

### Defining tools that require approval

![Tool approval code](images/slide_12.png)
[Watch from 09:32](https://www.youtube.com/watch?v=7pGqASn-LEY&t=572s)

Set `approval_mode` on the `@tool` decorator to control whether a tool requires human approval. Use `"never_require"` (the default) for read-only operations like `lookup_receipt`. Use `"always_require"` for write operations like `submit_expense_report`. Think of it in database terms: SELECT operations are generally safe, but UPDATE, INSERT, and DELETE operations are consequential and should require approval.

### Handling tool approval in the event loop

![Tool approval event loop](images/slide_13.png)
[Watch from 10:51](https://www.youtube.com/watch?v=7pGqASn-LEY&t=651s)

After calling `agent.run(query)`, check `result.user_input_requests` for pending approvals. There can be multiple requests if the agent triggered parallel tool calls. For each request, inspect `request.function_call` to see the tool name and arguments, then prompt the user for approval. Call `request.to_function_approval_response(approved)` to create the approval or rejection message, add it to the conversation, and rerun the agent with the updated messages.

In the demo, a simulated user asks the agent to look up receipts and submit an expense report. The lookup executes automatically (no approval needed), but the expense submission pauses for approval. When approved, the agent processes the approval and completes the task. When rejected, the agent must decide what to do — in this case it kept re-requesting, which highlights the need to handle rejections in the system prompt (e.g., instructing the agent to stop after a rejection) or via middleware that detects repeated rejected tool calls.

### Requests and responses

![Requests and responses section](images/slide_14.png)
[Watch from 15:32](https://www.youtube.com/watch?v=7pGqASn-LEY&t=932s)

Requests and responses are documented at [learn.microsoft.com/agent-framework/workflows/requests-and-responses](https://learn.microsoft.com/agent-framework/workflows/requests-and-responses).

### Requests and responses in workflows

![Request/response sequence diagram](images/slide_15.png)
[Watch from 15:32](https://www.youtube.com/watch?v=7pGqASn-LEY&t=932s)

Executors can pause a workflow and ask for human input using `ctx.request_info(data)`. The application code runs the workflow with `stream=True` and checks for events of type `"request_info"`. When one appears, the workflow is effectively paused. The application prompts the user, collects input, and calls `workflow.run(responses=pending)` with a dictionary mapping request IDs to human replies. Inside the executor, a method decorated with `@response_handler` receives the human's reply and resumes workflow execution.

### Simple chat with HITL: workflow topology

![Chat HITL topology](images/slide_16.png)
[Watch from 17:44](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1064s)

A simple chat workflow has two executors: a coordinator and an agent executor backed by an LLM. The coordinator receives the user's initial message and forwards it to the agent. When the agent responds, the coordinator calls `request_info` to ask the human for a reply. If the human replies with "done", the coordinator yields the final output and the workflow ends. Otherwise, the human's reply is sent back to the agent for another round.

### Executor code for handling requests and responses

![ChatCoordinator executor code](images/slide_17.png)
[Watch from 20:22](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1222s)

The `ChatCoordinator` executor uses two decorators. The `@handler` decorator on `on_agent_response` processes messages from the agent executor — when a response arrives, it calls `ctx.request_info()` to pause and ask the human for input. The `@response_handler` decorator on `on_human_reply` processes the human's response — if the reply is "done", it yields output and ends the workflow; otherwise, it sends the reply as a new message to the agent executor.

### App code for handling requests and responses

![Application event loop code](images/slide_18.png)
[Watch from 19:07](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1147s)

The application code streams events from the workflow. For each event, it checks the type: `"request_info"` events are collected into a pending dictionary keyed by request ID, and `"output"` events are printed. After processing all events, if there are pending requests, the application prompts the user for input, builds a response dictionary mapping request IDs to replies, and reruns the workflow with `workflow.run(stream=True, responses=pending)`.

### HITL with structured outputs: workflow topology

![Structured HITL topology](images/slide_19.png)
[Watch from 25:12](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1512s)

Instead of relying on free-text strings like "done" to drive flow control, this approach uses structured outputs. The agent responds with a `PlannerOutput` object that has a `status` field set to either `"need_info"` or `"complete"`. The coordinator checks the status: if `"need_info"`, it calls `request_info` with the agent's question; if `"complete"`, it yields the final output. This eliminates brittle string matching and makes flow decisions explicit and reliable.

### Agent definition with structured outputs

![PlannerOutput and agent definition](images/slide_20.png)
[Watch from 26:54](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1614s)

The `PlannerOutput` model is a Pydantic `BaseModel` with three fields: `status` (a `Literal["need_info", "complete"]`), an optional `question` string, and an optional `itinerary` string. The agent is configured with `response_format=PlannerOutput` in its default options, which forces the LLM to always produce JSON conforming to this schema. The system prompt should clearly specify what information the agent needs to collect before completing — destination, dates, activities, budget — so the agent systematically asks for each piece. Most frontier LLMs support structured outputs as part of their training process.

### Executor code for handling structured response

![TripCoordinator executor code](images/slide_21.png)
[Watch from 28:03](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1683s)

The `TripCoordinator` executor checks `result.agent_response.value` to get the parsed `PlannerOutput` object. If `output.status == "need_info"`, it calls `ctx.request_info` with the agent's question. If the status is `"complete"`, it yields the itinerary as the final output. The `@response_handler` method simply forwards the human's answer to the agent for the next iteration. The application event loop code is identical to the previous example — only the emoji differ.

In the demo, the trip planner agent systematically asked for destination, travel dates, budget, and preferred activities before producing a complete itinerary. The structured output ensured each round trip between agent and user was purposeful.

### Checkpoints and resuming

![Checkpoints section](images/slide_22.png)
[Watch from 32:27](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1947s)

Checkpoints are documented at [learn.microsoft.com/agent-framework/workflows/checkpoints](https://learn.microsoft.com/agent-framework/workflows/checkpoints).

### The need for checkpoints in HITL workflows

![Checkpoints comparison](images/slide_23.png)
[Watch from 32:27](https://www.youtube.com/watch?v=7pGqASn-LEY&t=1947s)

Without checkpoints, if a workflow pauses for human input and the human is unavailable, the process eventually crashes or exits and all progress is lost. With checkpoints, the workflow state is saved to disk or a database when it pauses. The process can safely exit. Hours later, a new process loads the checkpoint and the workflow resumes exactly where it left off. This is particularly important for HITL scenarios where the human may not respond immediately.

### Workflow lifecycle with checkpoints

![Checkpoint lifecycle diagram](images/slide_24.png)
[Watch from 33:48](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2028s)

In Process A, the workflow runs and calls `ctx.request_info()`. A checkpoint is saved containing: executor states, pending requests, messages, and shared state. Process A can then exit. In Process B, calling `workflow.run(checkpoint_id="chk1")` restores the checkpoint, re-emits the pending `request_info` event, and the workflow resumes. Checkpoints are saved after each step in the workflow, not only when requesting human input. The existing event processing loop does not need to change — any pending `request_info` events are automatically re-emitted upon restoration.

### Configuring checkpoint storage for workflows

![FileCheckpointStorage code](images/slide_25.png)
[Watch from 35:01](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2101s)

Agent framework provides `InMemoryCheckpointStorage` and `FileCheckpointStorage` as built-in options. To use file-based storage, create a `FileCheckpointStorage` with a directory path and pass it to `WorkflowBuilder` via the `checkpoint_storage` parameter. In production, you would typically associate checkpoints with a user or session to determine which checkpoint to resume.

### Resuming a workflow from checkpoint

![Resume from checkpoint code](images/slide_26.png)
[Watch from 35:45](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2145s)

Before running the workflow, check if a saved checkpoint exists. If one is found, pass its `checkpoint_id` to `workflow.run()` to resume from that point. If no checkpoint exists, start the workflow fresh with the initial input. The event processing loop remains unchanged — `request_info` events are re-emitted upon restoration.

In the demo, a content review workflow was started and then interrupted with Ctrl+C. The checkpoints directory showed three JSON files (one per workflow step). Re-running the script found the latest checkpoint, resumed the workflow, and re-emitted the pending approval request. After approval, the workflow completed. Running again found all six checkpoints and immediately completed since no work remained.

### Saving and restoring executor state

![on_checkpoint_save/restore code](images/slide_27.png)
[Watch from 39:19](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2359s)

When using checkpoints, executors that maintain instance state must implement `on_checkpoint_save` and `on_checkpoint_restore`. The save method returns a dictionary of the executor's state (e.g., `{"iteration": self._iteration}`), and the restore method rehydrates it. This ensures executor-specific state like iteration counters survives checkpoint/restore cycles.

### Designing your custom checkpoint storage

![CheckpointStorage protocol](images/slide_28.png)
[Watch from 41:06](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2466s)

To store checkpoints in any backend, implement the `CheckpointStorage` protocol with these methods: `save(checkpoint)` to persist a snapshot and return an ID, `load(checkpoint_id)` to restore by ID, `delete(checkpoint_id)` to remove a snapshot, `list_checkpoints(name)` to retrieve all snapshots for a workflow, `list_checkpoint_ids(name)` for just IDs, and `get_latest(name)` for the most recent snapshot. Built-in backends are `FileCheckpointStorage` (JSON files on disk) and `InMemoryCheckpointStorage` (in-process dict). Custom backends can use Redis, PostgreSQL, Cosmos DB, or anything else.

### Custom checkpoint storage design considerations

![Checkpoint design decisions](images/slide_29.png)
[Watch from 42:02](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2522s)

When designing custom checkpoint storage, consider several questions. **Scope**: should checkpoints be per workflow name, per user, or per session? You can scope by embedding identifiers in the workflow name (e.g., `"review:{user_id}"`). **Retention**: prune after completion, use TTL, or keep the N most recent? **Size**: checkpoints include full message history, so long conversations produce large JSONB blobs. **Access control**: who can access checkpoints? Consider row-level security or separate tables per tenant.

### Custom checkpoint storage with PostgreSQL

![PostgresCheckpointStorage code](images/slide_30.png)
[Watch from 42:02](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2522s)

The `PostgresCheckpointStorage` class creates a table with columns for `id`, `workflow_name`, `timestamp`, and `data`. It also creates an index on timestamp for efficient `get_latest` queries. The `save` method encodes the checkpoint (using pickle for Python objects), connects to the database with psycopg's `AsyncConnection`, and inserts a row. The `load` method selects by ID and decodes the data. The `list_checkpoints`, `delete`, and `get_latest` methods use standard SQL queries. Pickling is used here for serialization — this is acceptable since the data is under the application's control, but care should be taken with pickling untrusted data in general.

In the demo, the PostgreSQL-backed workflow was run, interrupted, and the VS Code PostgreSQL extension showed three checkpoint rows in the `workflow_checkpoints` table. Resuming found the latest checkpoint and completed the workflow, producing six total checkpoints.

### Handoff orchestration with HITL

![Handoff HITL section](images/slide_31.png)
[Watch from 47:42](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2862s)

Handoff orchestration with HITL is documented at [learn.microsoft.com/agent-framework/workflows/orchestrations/handoff](https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff).

### Review: handoff orchestration

![HandoffBuilder review](images/slide_32.png)
[Watch from 47:47](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2867s)

`HandoffBuilder` is a built-in workflow where agents can hand off to each other dynamically. No edges are defined up front — routing emerges from the conversation state. Handoff is inherently interactive: when an agent doesn't hand off, it requests user input. The workflow emits `HandoffAgentUserRequest` events that the application must handle for the workflow to continue. Handoff was covered in session 5 in autonomous mode (without users), but it works best with human-in-the-loop because agents often need additional information or guidance to decide what to do next.

### Configuring HandoffBuilder for interactivity

![HandoffBuilder configuration](images/slide_33.png)
[Watch from 49:00](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2940s)

`HandoffBuilder` is interactive by default — just do not call `with_autonomous_mode`. Create it with `name`, `participants` (a list of agents), and a `termination_condition` (a function that checks the conversation, e.g., terminating when anyone says "goodbye"). Set the `start_agent` to specify which agent handles the initial message.

### Handling HITL requests in HandoffBuilder

![HandoffBuilder HITL handling code](images/slide_34.png)
[Watch from 49:22](https://www.youtube.com/watch?v=7pGqASn-LEY&t=2962s)

Handle `HandoffAgentUserRequest` events similarly to generic `request_info` events but with handoff-specific methods. For each pending event, extract `agent_response` and display any text messages with their author name. Collect user input and build a response: `HandoffAgentUserRequest.terminate()` if the user wants to exit, or `HandoffAgentUserRequest.create_response(user_input)` otherwise. Rerun the workflow with `workflow.run(responses=responses, stream=True)`.

In the demo, a customer support handoff with triage, order, and return agents was tested. The triage agent handled initial routing, asked for an order number, and handed off to the return agent when the user requested a refund. The return agent processed the refund request, confirmed with the user, called a tool to process it, and handed back to triage. The termination condition triggered when an agent said "goodbye".

### End-to-end application

![E2E section divider](images/slide_35.png)
[Watch from 53:56](https://www.youtube.com/watch?v=7pGqASn-LEY&t=3236s)

This section demonstrates a full-stack application that combines handoff, tool approval, checkpoints, and multiple agents.

### Agentic banking assistant

![Banking assistant overview](images/slide_36.png)
[Watch from 53:56](https://www.youtube.com/watch?v=7pGqASn-LEY&t=3236s)

The agentic banking assistant is a sample application built with Agent Framework and FastMCP on the Python side, using Azure OpenAI, Azure Document Intelligence, and Azure Container Apps on the Azure side. The source code is at [github.com/Azure-Samples/agent-openai-python-banking-assistant](https://github.com/Azure-Samples/agent-openai-python-banking-assistant).

### Agents and MCP servers architecture

![Architecture diagram](images/slide_37.png)
[Watch from 54:35](https://www.youtube.com/watch?v=7pGqASn-LEY&t=3275s)

The application has four agents and three MCP servers. A **supervisor agent** (triage) understands user intent and routes requests to domain-specific agents via handoff. The **account agent** handles banking account info, credit balance, and payment methods using the account service MCP server. The **transaction agent** handles bank movements like income and outcome payments using both the account and reporting MCP servers. The **payment agent** handles bill payments using account, payments, and reporting MCP servers plus a `ScanInvoice` tool powered by Azure Document Intelligence for extracting entities from uploaded invoices. Azure OpenAI provides the GPT models for all agents.

### Handoff workflow with checkpointing

![Banking assistant HandoffBuilder code](images/slide_38.png)
[Watch from 56:02](https://www.youtube.com/watch?v=7pGqASn-LEY&t=3362s)

The banking assistant uses `HandoffBuilder` with all four agents as participants, the triage agent as the start agent, and `.with_checkpointing(checkpoint_storage)` to enable durable workflows. The application also integrates tool approval on the payment agent so that financial operations like submitting a payment require explicit user confirmation through the chat UI. The frontend uses OpenAI ChatKit for the interactive chat interface, and agent-framework provides an adapter to convert its output to ChatKit format.

In the demo, the assistant retrieved account transactions, listed payment methods, and processed a bill payment. For the bill payment, the user uploaded an invoice image, Document Intelligence extracted the payment details, the user confirmed accuracy, selected a payment method, and then a tool approval dialog appeared requiring explicit confirmation before the payment was submitted.

### Next steps and resources

![Next steps slide](images/slide_39.png)
[Watch from 1:00:51](https://www.youtube.com/watch?v=7pGqASn-LEY&t=3651s)

All past recordings and resources are available at [aka.ms/pythonagents/resources](https://aka.ms/pythonagents/resources). Office hours after each session are held in Discord at [aka.ms/pythonai/oh](https://aka.ms/pythonai/oh). Other series resources include [Python + AI series](https://aka.ms/pythonai/resources) and [Python + MCP series](https://aka.ms/pythonmcp/resources).

## Discord Office Hours Q&A

### What are some real-world use cases for the handoff with interaction pattern?

📹 [0:27](https://youtube.com/watch?v=FMi-SHU_55g&t=27)

The handoff pattern is designed for scenarios like a **phone tree** for customer service — where you have multiple specialist agents and the user gets routed to the right one. The key advantages over traditional phone trees:

- The **entire conversation history** gets passed between agents during handoff, so no context is lost.
- The **handoff is much faster** than waiting for a human to become available.

For handling offline users, you could use **database checkpoint storage** associated with the user. When a user revisits the site, you check if there's an in-progress workflow for them and resume it — similar to a chat history you can pick back up.

The important caveat is that handoff works best when specialist agents have **clearly defined, non-overlapping domains**. The banking assistant example works well because each agent has very specific responsibilities. The orders/returns demo was harder because those domains overlap too much, requiring significant prompt engineering to get the triage agent to route correctly.

Links shared:

* [Banking assistant sample (handoff with Foundry agents)](https://github.com/Azure-Samples/agent-openai-python-banking-assistant/tree/main/app/backend/app/agents/foundry_v2)
* [Handoff documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff?pivots=programming-language-python)

### When building agents, does it make sense to use MCP or just use the underlying Python methods?

📹 [4:28](https://youtube.com/watch?v=FMi-SHU_55g&t=268)

This is an architectural decision. MCP is useful for **reusability and portability**, but you shouldn't make something an MCP server unless you plan to use it in **multiple contexts**.

Consider using MCP when:

- You want to reuse the same tools across **different agents or applications**
- You intend to use the tools in a **generic MCP client** like VS Code or Claude, where MCP capabilities beyond tools (like elicitations for asking users for more info) become valuable
- You want **portability across your organization**

If your agent just needs access to some API calls and you don't have reasons for portability, **keep them as plain tools**. When used solely from your own agents, you're likely only using the tools aspect of MCP anyway — you lose the benefit of the richer MCP protocol features like elicitations.

### How do you create a human-in-the-loop workflow in an API using checkpoints?

📹 [6:26](https://youtube.com/watch?v=FMi-SHU_55g&t=386)

Checkpoints are needed for **resuming workflows over time** (e.g., between process restarts or when a human is offline). If the human is present the whole time, you don't necessarily need checkpoints.

For workflows that occasionally need human intervention, the pattern is:

1. **Run the workflow** and detect when human input is needed
2. **Save a checkpoint** and exit when no human is available
3. Use an **inbox-style UI** to surface all paused workflows that need action
4. **Resume from checkpoint** once the human takes action

An example of this pattern is [LangChain's agent inbox](https://github.com/langchain-ai/agent-inbox), a React app that finds all interrupted agent threads and surfaces them for human action. A similar approach could be built for Agent Framework using database checkpoint storage, tracking workflow completion status, and displaying pending workflows.

There's also the [DBOS durable execution approach](https://docs.dbos.dev/python/examples/agent-inbox) for human-in-the-loop workflows, which handles durability differently.

### How do we find out what executors in a sequential workflow send to another executor?

(Not captured in video recording)

You can monitor the messages using the events from a streaming worklow execution. When you run a workflow with `stream=True`, you get an event stream that includes messages sent between executors, and includes each time an output is added to the workflow outputs. Once the workflow ends, query `get_outputs()` for the final list of outputs.

Typically, the executors _inside_ a workflow will use `send_message`, and the final executor will use `yield_output`, but executors can also yield outputs along the way (in addition to sending messages).

### How do we protect our API keys and tokens from GitHub Copilot agent mode?

(Not captured in video recording)

GitHub Copilot agent mode has access to your code, so you need to be careful about how you store secrets. It will generally not edit a `.env` file if you have one, but it can read from it and potentially expose secrets in generated code or during screen sharing.

- Consider using **keyless authentication** (like Azure managed identity / DefaultAzureCredential) to avoid needing API keys at all.
- For **local development**, storing tokens in a `.env` file (excluded via `.gitignore`) is acceptable. If you're uncomfortable with that, consider using a local secrets manager (e.g. the Python `keyring` library for Mac or [Infisical](https://github.com/Infisical/infisical).)
- For **production**, use a secrets manager like Azure Key Vault.
- To avoid **accidentally exposing secrets during screen sharing**, keep `.env` files closed and consider the VS Code [Camouflage extension](https://marketplace.visualstudio.com/items?itemName=KnisterPeter.camouflage). You can also move secrets to the very end of the file, after many blank lines, to reduce the chance of accidental exposure.

### What is your opinion on agent-skills (experimental) vs using workflows in Agent Framework?

(Not captured in video recording)

Pamela has an example of using Microsoft Agent Framework with skills in her [presentation write-up repository](https://github.com/pamelafox/presentation-writeups/blob/main/agent_skills.py). Typically she uses GitHub Copilot agent with the repo's skills, but for further automation, she can use the Agent Framework agent with the same skills. This way, the skills can be shared between both approaches.

When an agent is given skills, it can be very creative and flexible in how it uses them, which is great for open-ended tasks. However, if you have a more structured process in mind, using the Agent Framework with defined workflows can give you more control over the orchestration and flow of the task.

Check the [MAF documentation on skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python) for more examples and a good discussion of the pros and cons of each approach.
