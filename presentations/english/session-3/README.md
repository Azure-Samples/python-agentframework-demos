# Python + Agents (Session 3): Monitoring and evaluating agents

📺 [Watch the full recording on YouTube](https://www.youtube.com/watch?v=3yS-G-NEBu8) |
📑 [Download the slides (PDF)](https://aka.ms/pythonagents/slides/monitoreval)

This write-up includes an annotated version of the presentation slides with timestamps to the video plus a summary of the live Q&A sessions.

## Table of contents

- [Session description](#session-description)
- [Annotated slides](#annotated-slides)
  - [Overview of the Python and Agents series](#overview-of-the-python-and-agents-series)
  - [Monitoring and evaluating agents](#monitoring-and-evaluating-agents)
  - [Agenda: monitoring, evaluation, and safety](#agenda-monitoring-evaluation-and-safety)
  - [Following along with the GitHub repo and Codespaces](#following-along-with-the-github-repo-and-codespaces)
  - [Recap: what is an AI agent](#recap-what-is-an-ai-agent)
  - [Monitoring agents](#monitoring-agents)
  - [Observability with OpenTelemetry](#observability-with-opentelemetry)
  - [Using OpenTelemetry with Agent Framework](#using-opentelemetry-with-agent-framework)
  - [OTel-compliant observability platforms](#otel-compliant-observability-platforms)
  - [Exporting to the Aspire dashboard](#exporting-to-the-aspire-dashboard)
  - [Monitoring agent traces and metrics in Aspire](#monitoring-agent-traces-and-metrics-in-aspire)
  - [Standard trace format for agent executions](#standard-trace-format-for-agent-executions)
  - [Exporting OpenTelemetry to Azure Application Insights](#exporting-opentelemetry-to-azure-application-insights)
  - [Viewing traces in Azure Application Insights](#viewing-traces-in-azure-application-insights)
  - [Evaluating agents](#evaluating-agents)
  - [Agent output is non-deterministic](#agent-output-is-non-deterministic)
  - [Evaluating agent outputs: human grading](#evaluating-agent-outputs-human-grading)
  - [Automated evaluation with LLMs](#automated-evaluation-with-llms)
  - [Automated evaluation frameworks](#automated-evaluation-frameworks)
  - [Using the azure-ai-evaluation package](#using-the-azure-ai-evaluation-package)
  - [Built-in evaluators for AI agents](#built-in-evaluators-for-ai-agents)
  - [Tool call accuracy evaluator](#tool-call-accuracy-evaluator)
  - [Intent resolution evaluator](#intent-resolution-evaluator)
  - [Task adherence evaluator](#task-adherence-evaluator)
  - [Response completeness evaluator](#response-completeness-evaluator)
  - [Bulk evaluation of a dataset](#bulk-evaluation-of-a-dataset)
  - [Viewing evaluation results locally](#viewing-evaluation-results-locally)
  - [Viewing evaluation results in AI Foundry](#viewing-evaluation-results-in-ai-foundry)
  - [CI/CD evaluation with GitHub Actions](#cicd-evaluation-with-github-actions)
  - [Dev loop for AI agents](#dev-loop-for-ai-agents)
  - [Safety evaluation](#safety-evaluation)
  - [What makes an agent's output safe?](#what-makes-an-agents-output-safe)
  - [Automated red teaming process](#automated-red-teaming-process)
  - [Configuring the red-teaming agent](#configuring-the-red-teaming-agent)
  - [Running the red-teaming scan](#running-the-red-teaming-scan)
  - [Reviewing red team results](#reviewing-red-team-results)
  - [When to run red team scans](#when-to-run-red-team-scans)
  - [Next steps and resources](#next-steps-and-resources)
- [Live Chat Q&A](#live-chat-qa)
- [Discord Office Hours Q&A](#discord-office-hours-qa)

## Session description

In the third session of the Python + Agents series, we shifted focus to two essential components of building reliable agents: observability and evaluation.

We began with observability, using OpenTelemetry to capture traces, metrics, and logs from agent actions. We showed how to instrument agents built with the Microsoft Agent Framework and export telemetry to local dashboards (Aspire) and managed platforms (Azure Application Insights), using the standard `gen_ai` OpenTelemetry attributes to get rich trace rendering.

From there, we explored how to evaluate agent behavior using the Azure AI Evaluation SDK. We covered four built-in evaluators—tool call accuracy, intent resolution, task adherence, and response completeness—running them both individually and in bulk against data sets, with results viewable locally or in Microsoft Foundry.

We concluded with safety evaluation through automated red teaming, using adversarial LLMs to test whether agents could withstand attacks like URL encoding, tense transformation, and other jailbreak strategies.

## Annotated slides

### Overview of the Python and Agents series

![Series overview slide](images/slide_1.png)
[Watch from 00:58](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=58s)

This series consists of six sessions teaching how to build AI agents using the Microsoft Agent Framework. Session 3 marks the end of week one, which covers building individual agents. Week two focuses on building multi-agent workflows. Recordings, write-ups, and slides from previous sessions are available through the series resources link, and registering for the series provides email notifications for upcoming sessions.

### Monitoring and evaluating agents

![Session title slide](images/slide_2.png)
[Watch from 01:42](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=102s)

This session covers monitoring and evaluating agents—two essential capabilities for production agent systems. Monitoring provides visibility into what an agent is doing, while evaluation ensures the agent is producing high-quality outputs.

### Agenda: monitoring, evaluation, and safety

![Agenda slide](images/slide_3.png)
[Watch from 01:53](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=113s)

The agenda covers three topics: monitoring agents using OpenTelemetry and exporting telemetry to platforms like Aspire and Azure Application Insights; evaluating agents using the Azure AI Evaluation SDK with built-in evaluators for tool call accuracy, intent resolution, task adherence, and response completeness; and safety evaluation through automated red teaming to ensure agents do not produce harmful outputs.

### Following along with the GitHub repo and Codespaces

![Instructions for following along](images/slide_4.png)
[Watch from 02:41](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=161s)

All code for the session is in the same GitHub repository used throughout the series. Creating a GitHub Codespace from the repository provides a preconfigured VS Code environment with Python dependencies and examples. A `git pull` is recommended after starting the Codespace to get the latest changes. Unlike previous sessions, some examples in this session require Azure resources that are not free—specifically Azure Application Insights and Microsoft Foundry—so not all examples can be run entirely for free in Codespaces.

### Recap: what is an AI agent

![Agent definition recap](images/slide_5.png)
[Watch from 04:23](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=263s)

An AI agent uses an LLM to achieve a goal by calling tools in a loop. The LLM decides which tools to invoke and continues calling tools until it has enough information to produce a response. Agent runs are non-deterministic—some complete with zero tool calls, others may need twenty. This variability in behavior is precisely why monitoring and evaluation are essential: you need to see what the agent actually did and verify it was correct.

### Monitoring agents

![Monitoring agents section slide](images/slide_6.png)
[Watch from 06:20](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=380s)

Observability is critical for any user-facing application, but even more important for agents because of their non-deterministic nature. Agents have agency—they choose which tools to call, in what order, and with what arguments. Monitoring lets you observe what the agent actually chose to do and whether those choices led to good outcomes.

### Observability with OpenTelemetry

![OpenTelemetry overview](images/slide_7.png)
[Watch from 06:57](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=417s)

OpenTelemetry (OTel) is an open standard for observability and the most widely supported standard across the industry. It defines how applications should emit three types of signals: **traces** (sequences of spans showing how a request moves through services, including timing and dependencies), **metrics** (numerical measurements like CPU usage, request counts, and latency for graphing), and **logs** (structured log records with message, severity, timestamp, and contextual attributes). Using OpenTelemetry means you can export to many different observability platforms without vendor lock-in.

### Using OpenTelemetry with Agent Framework

![Agent Framework OTel code](images/slide_8.png)
[Watch from 08:14](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=494s)

The Microsoft Agent Framework has built-in support for generating OpenTelemetry traces. Enabling it requires importing `configure_otel_providers` from the agent framework and calling it with configuration options. The `enable_sensitive_data` parameter controls whether detailed data like tool call arguments and messages is included in traces—this involves a privacy trade-off where more data enables better debugging but may include private user information. Setting `ENABLE_CONSOLE_EXPORTERS=true` as an environment variable outputs traces directly to the terminal, which is useful for verifying instrumentation works before configuring an external exporter. The demo shows spans for each tool execution, LLM chat completion calls, and metrics for token usage—though reading raw JSON in a console is not practical for real development.

### OTel-compliant observability platforms

![OTel-compliant platforms table](images/slide_9.png)
[Watch from 13:59](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=839s)

Many observability platforms support OpenTelemetry. **Aspire** is an open-source local dashboard without a managed version. **Azure Application Insights** is a managed service commonly used for Azure deployments. Other options include Datadog, Grafana (now integrated within App Insights), Prometheus, Jaeger, and **Logfire** from the creators of Pydantic, which has a particularly nice UI. All are OpenTelemetry-compliant, so switching between them requires only changing the exporter configuration.

### Exporting to the Aspire dashboard

![Aspire dashboard setup](images/slide_10.png)
[Watch from 15:18](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=918s)

Exporting to the Aspire dashboard requires setting the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable to the Aspire server's address and the `OTEL_EXPORTER_OTLP_PROTOCOL` to `grpc`. The `opentelemetry-exporter-otlp-proto-grpc` package must be installed (already included in the project's `pyproject.toml`). In the session's GitHub Codespace, Aspire runs as a Docker service inside the dev container with the endpoint already configured. The code simply calls `configure_otel_providers` as before—the function reads the environment variables automatically.

### Monitoring agent traces and metrics in Aspire

![Aspire dashboard monitoring](images/slide_11.png)
[Watch from 18:00](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1080s)

The Aspire dashboard displays three types of data: **traces** (agent executions, LLM calls, and tool calls), **metrics** (tool call durations, LLM call durations, and token usage), and **logs** (Python logging calls). Clicking on a trace reveals its spans in a timeline view—a typical agent trace shows an initial chat completion call where the LLM decides which tools to call, the individual tool execution spans, and a final chat completion call where the LLM generates its response. The timeline makes it clear that LLM calls dominate total duration. Aspire also renders LLM conversations in a developer-friendly format by recognizing the `gen_ai` OpenTelemetry standard attributes—clicking the sparkle icon shows the full conversation including system prompt, user query, tool call decisions, and assistant response. The metrics tab graphs token usage and operation durations over time, useful for identifying patterns and slow tools.

### Standard trace format for agent executions

![Gen AI standard trace attributes](images/slide_12.png)
[Watch from 28:02](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1682s)

Agent Framework uses the standard `gen_ai` span attribute names and values for agent executions, LLM calls, and tool calls. For example, a tool call span includes attributes like `gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.tool.call.arguments`, and `gen_ai.tool.call.result`. This is an OpenTelemetry standard specifically for generative AI applications—both Aspire and App Insights can render rich, conversational views of traces because they recognize this standard, not because they have specific knowledge of Agent Framework. Any observability platform that supports the Gen AI OpenTelemetry standard will provide similar rich rendering. The Agent Framework documentation lists the specific spans it generates (`invoke_agent`, `chat`, `execute_tool`) and built-in metrics (operation duration, token usage, invocation duration), with the ability to add custom spans and metrics using standard OpenTelemetry APIs.

### Exporting OpenTelemetry to Azure Application Insights

![App Insights OTel setup](images/slide_13.png)
[Watch from 23:28](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1408s)

Azure Application Insights is a managed observability platform for production use. It requires the `azure-monitor-opentelemetry` package (already in the project's `pyproject.toml`). The setup imports `configure_azure_monitor` and calls it with the Application Insights connection string from environment variables, a resource name from the agent framework's `create_resource()`, and `enable_live_metrics=True`. Then `enable_instrumentation` from the agent framework wires up the exporter with an option to include sensitive data. This configuration means whenever Agent Framework generates OpenTelemetry traces, they automatically get exported to App Insights. Unlike the free GitHub Models used in previous sessions, App Insights requires an Azure resource that is not free.

### Viewing traces in Azure Application Insights

![App Insights trace view](images/slide_14.png)
[Watch from 25:05](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1505s)

The App Insights trace view looks similar to Aspire, showing the same pattern: an invoke agent parent span, initial chat completion call, tool call spans, and final chat completion call. The Performance tab with Dependencies view is the easiest way to find recent traces. App Insights also renders LLM conversations in a friendly format rather than raw JSON, thanks to the Gen AI OpenTelemetry standard. There may be up to a five-minute lag between an event occurring and it appearing in App Insights. Once telemetry data is flowing, you can set up dashboards, alerts, and custom queries to monitor agent behavior in production.

### Evaluating agents

![Evaluating agents section slide](images/slide_15.png)
[Watch from 31:40](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1900s)

Evaluation ensures agents produce high-quality outputs. While it is easy to build agents, it is harder to build agents that consistently perform well. Evaluation provides the rigor needed to verify quality and catch regressions when changing models, prompts, or tools.

### Agent output is non-deterministic

![Non-determinism in agent output](images/slide_16.png)
[Watch from 33:06](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=1986s)

Each LLM call increases non-determinism and risk. A high-quality agent must choose the right tools, in the right order, with the right arguments, and then generate a response grounded in those tool call results without missing or fabricating information. Any change to the model version, temperature, or prompt can affect output quality—sometimes for better, sometimes for worse. "Vibe checks" are fine initially, but must be verified with automated evaluation to detect regressions.

### Evaluating agent outputs: human grading

![Human grading approach](images/slide_17.png)
[Watch from 33:47](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2027s)

Human grading involves domain experts spot-checking agent output performance on small data sets, rating responses with thumbs up/down and annotating issues. Humans are particularly valuable for explaining *why* something is wrong, which informs what automated evaluations to build. Human evaluators must have domain expertise—LLMs can be convincingly wrong, and only experts can catch subtle hallucinations. Some form of human evaluation is always recommended alongside automated approaches.

### Automated evaluation with LLMs

![Automated evaluation overview](images/slide_18.png)
[Watch from 35:16](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2116s)

Automated evaluation uses LLMs to measure output performance at scale across a broader range of risks. Once set up, automated evaluation can run whenever the system changes, enabling confident model and prompt changes. It scales to much larger data sets than human grading. The combination of human annotation to identify issues and automated evaluation to prevent regressions is the recommended approach.

### Automated evaluation frameworks

![Evaluation frameworks table](images/slide_19.png)
[Watch from 35:54](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2154s)

Multiple frameworks support automated evaluation:

- **Azure AI Evaluation / Microsoft.Extensions.AI.Evaluation** (Python and .NET) — the focus of this session, with optional cloud hosting via AI Foundry
- **Tau** (Python) — from Sierra, specifically designed for customer service agents
- **RAGAS** (Python) — from ExplodingGradients, a research-based startup
- **DeepEval** (Python) — from ConfidentAI, includes an optional hosted evaluation service
- **Langsmith** (Python) — from LangChain, requires their cloud platform
- **OpenAI evals** (Python) — built into the OpenAI package, now integrates with both openai.com and Microsoft Foundry

### Using the azure-ai-evaluation package

![Azure AI Evaluation package overview](images/slide_20.png)
[Watch from 37:22](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2242s)

Installing the `azure-ai-evaluation` package provides access to built-in evaluators for quality and safety, the ability to build custom evaluators for any criteria, bulk evaluation functionality, an automated red-teaming agent, and the option to save results in AI Foundry. The package is installed in `pyproject.toml`, including the `[redteam]` sub-package for red teaming later in the session. Evaluations use tokens and take time since they rely on LLM-as-a-judge, so they should be run thoughtfully rather than on every code change.

### Built-in evaluators for AI agents

![Built-in evaluators diagram](images/slide_21.png)
[Watch from 37:59](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2279s)

Agents should be evaluated at multiple levels using four built-in evaluators. **ToolCallAccuracyEvaluator** checks whether the agent invoked the right tools with the right arguments. **IntentResolutionEvaluator** checks whether the agent achieved the user's goal. **TaskAdherenceEvaluator** checks whether the agent followed prompt constraints and tool-use rules. **ResponseCompletenessEvaluator** checks whether the response includes all required information from a ground truth response. All use LLM-as-a-judge, where another LLM evaluates the agent's output. Running multiple evaluators is important because they catch different types of issues—the same problem may be scored differently by different evaluators.

### Tool call accuracy evaluator

![Tool call accuracy code](images/slide_22.png)
[Watch from 41:33](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2493s)

The `ToolCallAccuracyEvaluator` from the Azure AI Evaluation SDK checks whether the agent invoked the right tools with the right arguments and didn't make unnecessary calls. It requires the most detailed input: the system prompt, user query, all tool calls and results in the conversation, JSON schema definitions of available tools, and the final response. The LLM judge scores from 1 to 5 and provides a reason. This granular evaluator is especially useful for diagnosing why high-level evaluators gave low scores—if the agent failed to achieve the user's goal, tool call accuracy can reveal whether the root cause was calling the wrong tool or using incorrect arguments.

### Intent resolution evaluator

![Intent resolution code](images/slide_23.png)
[Watch from 44:03](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2643s)

The `IntentResolutionEvaluator` assesses how well the agent identified and fulfilled the user's request, including how well it scoped the user's intent, asked clarifying questions, and reminded end users of its capabilities. It takes the full conversation and response as input but does not require tool call definitions. It scores from 1 to 5. There is an ongoing debate about whether scores should be 1-to-5 or binary (pass/fail)—with 1-to-5 scoring, most people consider 4 and 5 to be passing, but binary scoring eliminates ambiguity about what counts as a pass.

### Task adherence evaluator

![Task adherence code](images/slide_24.png)
[Watch from 45:10](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2710s)

The `TaskAdherenceEvaluator` checks whether the agent followed the constraints specified in the system message and tool-use rules. In the session's demo, both intent resolution and task adherence detected the same issue (an inconsistent travel date), but scored it differently: intent resolution gave a 4 (mostly achieved the goal), while task adherence gave a 0 (violated a constraint). This demonstrates why running multiple evaluators matters—different evaluators weight the same issue differently based on what they're measuring.

### Response completeness evaluator

![Response completeness code](images/slide_25.png)
[Watch from 45:57](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2757s)

The `ResponseCompletenessEvaluator` compares the agent's response against a ground truth—the ideal answer for a given question. This requires a data set where each query has a known correct response. Ground truth evaluation is the strongest check against hallucinations because it verifies that all expected information is present. Building evaluation data sets with ground truth is strongly recommended, as it provides the most reliable quality signal.

### Bulk evaluation of a dataset

![Bulk evaluation code](images/slide_26.png)
[Watch from 51:43](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3103s)

For production evaluation, use the `evaluate()` function to process a JSONL file containing previous agent runs against all desired evaluators at once. A typical evaluation data set should have around 200 runs to be thorough and representative. The data can be generated by running the agent and saving outputs, or captured from real production interactions. It is critical to continuously add production examples—especially failed cases found through OpenTelemetry monitoring—to prevent model drift where evaluations no longer reflect real-world usage.

### Viewing evaluation results locally

![Local evaluation results](images/slide_27.png)
[Watch from 56:00](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3360s)

Evaluation results are saved as JSON files that can be viewed locally. For a nicer experience, you can build a custom CLI viewer using Python libraries like Rich or Textual—the presenter suggests asking GitHub Copilot to help build one. Individual evaluations (like the `agent_evaluation.py` demo shown earlier at [46:22](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=2782s)) display each evaluator's score and reason directly in the terminal, which is useful for quick checks during development.

### Viewing evaluation results in AI Foundry

![AI Foundry evaluation results](images/slide_28.png)
[Watch from 53:43](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3223s)

Passing an `azure_ai_project` parameter to `evaluate()` exports results to an Microsoft Foundry project for viewing and sharing. The Foundry portal (currently only the classic UI supports viewing locally-run Python evaluation results) shows pass rates across all evaluators, individual scores with reasons, and drill-down into each run. This enables collaboration—share evaluation runs with colleagues to review failures and discuss improvements.

### CI/CD evaluation with GitHub Actions

![CI/CD evaluation setup](images/slide_29.png)
[Watch from 56:11](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3371s)

Evaluations can run from a GitHub Actions workflow and display results directly in pull requests. However, evaluations are expensive (they require many LLM calls) and slow (hundreds of runs with multiple evaluators can take an hour). A practical approach is to trigger evaluations with a specific PR comment (e.g., `/eval`) rather than running on every PR, giving developers control over when to invest in a full evaluation pass.

### Dev loop for AI agents

![Dev loop diagram](images/slide_30.png)
[Watch from 56:30](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3390s)

The complete agent development loop progresses through three stages: **ideating/exploring** (identifying the use case, connecting tools, customizing prompts), **building/augmenting** (running the agent against sample questions, trying different parameters, evaluating against larger datasets), and **productionizing** (deploying to users, collecting feedback, running online evaluations, and A/B experiments). The key insight is that observability and evaluation work together—OpenTelemetry monitoring reveals what agents are doing in production, and evaluation ensures changes improve rather than regress quality. Online evaluations (running evaluators on a subset of live traffic without ground truth) can also be configured for continuous monitoring.

### Safety evaluation

![Safety evaluation section slide](images/slide_31.png)
[Watch from 57:24](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3444s)

Beyond quality, agents must also produce safe outputs. Safety evaluation ensures that adversarial users cannot manipulate the agent into generating harmful content.

### What makes an agent's output safe?

![Safety risks overview](images/slide_32.png)
[Watch from 57:55](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3475s)

An agent should not produce output that harms users, reduces trust in the organization, or breaks laws. Specific risks include generating hateful or unfair speech, encouraging violence or self-harm, producing sexual content (though acceptable levels may vary for health/medical apps), allowing access to protected materials, and changing behavior due to jailbreak attacks.

### Automated red teaming process

![Red teaming architecture diagram](images/slide_33.png)
[Watch from 58:09](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3489s)

Automated red teaming simulates human red teaming using the `azure-ai-evaluation` SDK. An adversarial LLM with all guardrails removed generates harmful questions and transforms them with common attack strategies (text reversal, Morse code, Caesar cipher, URL encoding). These are sent to the target agent, and a separate Risk and Safety evaluator LLM judges whether the response was safe. A safe response means the attack failed; an unsafe response means the attack succeeded. The goal is zero successful attacks.

### Configuring the red-teaming agent

![RedTeam class configuration](images/slide_34.png)
[Watch from 59:16](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3556s)

The `RedTeam` class requires an Microsoft Foundry project because the adversarial LLM is only accessible through Foundry—its guardrails are removed, so access is restricted to this evaluation purpose. Configuration includes the Foundry project endpoint, credential, risk categories to test (Violence, HateUnfairness, Sexual, SelfHarm), and the number of adversarial questions per category.

### Running the red-teaming scan

![Red team scan execution](images/slide_35.png)
[Watch from 01:00:01](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3601s)

The `scan` method runs the red-teaming attack with specified strategies. **Baseline** sends unmodified adversarial questions. **URL encoding** uses `%20`-style encoded text—a surprisingly effective attack. **Tense transformation** rephrases questions as historical queries. Strategies can be composed together for more complex attacks. The scan runs multiple attacks with different transformations against the target callback function and saves results to a JSON file.

### Reviewing red team results

![Red team results review](images/slide_36.png)
[Watch from 01:00:33](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3633s)

Red team results can be viewed locally or in AI Foundry's evaluation tab under red teaming. Results show attack success rates by category—for example, 3 out of 50 sexual content attacks might succeed. Individual results can be inspected to see the adversarial prompt and the agent's response. Be warned: reviewing successful attacks means reading offensive and potentially triggering content—the adversarial prompts are deliberately harmful and disturbing.

### When to run red team scans

![When to run red teams](images/slide_37.png)
[Watch from 01:01:49](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3709s)

Red teaming scans take time, so don't run them on every code change. Do run them on model changes or non-trivial prompt changes. Results vary significantly across models—the presenter's blog post comparing models showed GPT-4o-mini on Azure OpenAI with 0% attack success rate, Llama 3.1 8B on Ollama with 2%, and Hermes 3 3B on Ollama with 13%. Changes to tool definitions and prompts can also affect safety, so rerunning scans after significant changes is recommended.

### Next steps and resources

![Next steps closing slide](images/slide_38.png)
[Watch from 01:02:27](https://www.youtube.com/watch?v=3yS-G-NEBu8&t=3747s)

The session concludes with an invitation to Discord office hours for additional questions. Next week (sessions 4–6) covers multi-agent workflows with the Agent Framework. All previous session recordings, write-ups, and slides are available through the series resources page, and registration provides notifications for upcoming sessions.

## Live Chat Q&A

### Does OpenTelemetry add latency to the agent?

Exporting telemetry does add some latency because it involves a network request to the observability platform. However, these requests are fast compared to LLM calls, and observability platforms are designed for high throughput. To reduce overhead in high-traffic environments, set a sampling rate—for example, only export 1% or 5% of traces. The overhead is low relative to the dominant cost of LLM calls.

### Is the Agent Framework setting up the metrics automatically?

Yes. The Agent Framework generates spans (`invoke_agent`, `chat`, `execute_tool`) and metrics (operation duration, token usage, invocation duration) automatically when `configure_otel_providers` is called. Additional custom spans and metrics can be added using standard OpenTelemetry APIs. If using other frameworks (FastAPI, Azure Python SDK), their OpenTelemetry instrumentations should also be enabled for complete coverage.

### Should scores be binary or 1-to-5?

There is active debate in the evaluation community. The Azure AI Evaluation SDK uses 1-to-5 scoring, where most people consider 4 and 5 as passing. Some practitioners argue binary (pass/fail) is better because it eliminates ambiguity about what score constitutes a pass. For custom evaluators, either approach works—choose based on whether the granularity of 1-to-5 scores provides useful signal for your use case.

### How did you generate the evaluation data set?

The `agent_evaluation_generate.py` script runs the agent on a set of queries and saves the full conversation (including tool calls) to a JSONL file. For the demo, the queries were generated using GitHub Copilot. In production, the best evaluation data comes from real user interactions—especially examples where the agent performed poorly. Until production data is available, LLM-generated synthetic data is a reasonable starting point that should be replaced over time.

### Can evaluations run in CI/CD?

Yes. The Azure AI Evaluation SDK can be used in GitHub Actions. However, evaluations are expensive (they require many LLM calls) and slow (hundreds of runs with multiple evaluators can take an hour). A practical approach is to trigger evaluations with a specific pull request comment (e.g., `/eval`) rather than running them on every PR. This gives developers control over when to invest in a full evaluation pass.

## Discord Office Hours Q&A

### Do you need an Azure account to use the Azure AI evaluation SDK, and is there a free level?

📹 [0:56](https://youtube.com/watch?v=D9vfGeoPh_I&t=56)

You don't necessarily need an Azure account for the quality evaluations. The local evaluation SDK works with any OpenAI-compatible model — you just need to set up the model configuration. In theory, you can use it with OpenAI.com, or even run it locally with Ollama if you have a capable enough machine and model.

The main limitation with GitHub Models is the token cap — some attendees hit limits, though Pamela managed to run evaluations with GPT-5 Mini on GitHub Models.

For the batch evaluation, the Azure AI project parameter is optional — you can output results locally. However, for **red teaming**, you do need a Foundry project because it requires access to the adversarial LLM.

There's also a newer way of doing evals using the OpenAI SDK in conjunction with the Azure AI Projects SDK, but that does require a Foundry project.

### Does a Microsoft 365 Family subscription include any tokens for Foundry or Azure?

📹 [9:01](https://youtube.com/watch?v=D9vfGeoPh_I&t=541)

No — M365 licenses are independent of Azure subscriptions. You'd need to set up an Azure account separately. Azure free trial accounts have very limited Foundry model access (around 1,000 tokens capacity) and likely can't create Foundry projects. The recommendation is to create a regular Azure account, set a budget limit (e.g., $20/month), and configure a budget alert.

### How do you set up custom spans within traces in OpenTelemetry?

📹 [5:01](https://youtube.com/watch?v=D9vfGeoPh_I&t=301)

When using the Agent Framework, spans are automatically set up for you. For custom spans, you create a tracer and use a context manager (`with` statement) to define a parent span, then set attributes on that span. Children spans created within that context automatically nest under the parent.

An example of this approach is the [OpenTelemetry middleware for MCP servers](https://github.com/Azure-Samples/python-mcp-demos/blob/main/servers/opentelemetry_middleware.py), which sets up a tracer provider and creates spans with attributes for each request.

Links shared:

* [OpenTelemetry middleware example](https://github.com/Azure-Samples/python-mcp-demos/blob/main/servers/opentelemetry_middleware.py)

### What if I get a deployment error because my Azure account doesn't have Owner access?

📹 [7:45](https://youtube.com/watch?v=D9vfGeoPh_I&t=465)

The keyless credential setup in the demo repo requires certain roles (like Owner) to create role assignments. If you only have Contributor access, you'll hit errors. Workarounds:

1. Get RBAC Owner access scoped to just a resource group and deploy to that group
2. Set up the resources manually instead of using the repo's infrastructure-as-code
3. Check the [Azure account requirements](https://github.com/Azure-Samples/azure-search-openai-demo/?tab=readme-ov-file#azure-account-requirements) for details on needed roles

Also, make sure the model version in the Bicep matches a supported version — one attendee fixed a deployment error by updating `main.bicep` to deploy `gpt-5-mini` instead of `gpt-4.1-mini`.

### Why did the LLM take 5 seconds to decide on tools?

📹 [10:28](https://youtube.com/watch?v=D9vfGeoPh_I&t=628)

LLMs have inherent latency, especially reasoning models like GPT-5 Mini. Several factors affect response time:

- **Deployment type**: Pay-as-you-go (standard) has higher latency than provisioned deployments, which give you dedicated infrastructure
- **Reasoning effort**: You can set a `reasoning_effort` parameter (low/medium/high) to trade off thinking time vs. speed. In the Agent Framework, pass it via `default_options` when creating the agent
- **Model choice**: Newer model versions (5.1, 5.2, etc.) are often faster than their predecessors at similar quality levels
- **Variability**: Never base performance conclusions on a single call — use load testing (e.g., [Locust](https://locust.io/)) and look at percentiles (P50, P99)

Pamela demonstrated measuring latency across evaluation runs using a custom [Textual](https://textual.textualize.io/)-based CLI tool, showing how latency varies significantly across models and runs.

### What about adding a validation/checker agent to improve quality?

📹 [16:50](https://youtube.com/watch?v=D9vfGeoPh_I&t=1010)

Adding a reflection/validation step doubles latency since it's another LLM call. Alternatives:

- Ask the LLM to self-report a **confidence level** in its response — surprisingly, LLMs can accurately indicate low confidence
- Only trigger a reflection step when confidence is low
- Use evaluation to verify that the extra step actually improves quality — in Pamela's RAG experiments, a naive reflection loop often didn't improve answers

Links shared:

* [Locust load testing](https://locust.io/)
* [Textual TUI framework](https://textual.textualize.io/)
* [Azure OpenAI model availability table](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure?view=foundry-classic&pivots=azure-openai&tabs=global-standard-aoai%2Cglobal-standard#models-by-deployment-type)

### Is Microsoft Agent Framework GA yet? What's recommended for production today?

📹 [32:27](https://youtube.com/watch?v=D9vfGeoPh_I&t=1947)

Not yet GA — the latest release is 1.0.0 RC2 (release candidate 2), released just 19 hours before the session. It's very close to GA, likely weeks away. The agent API was expected to be stable by end of February, with the workflow API potentially seeing minor changes into March.

For customers wanting to build production agentic apps now, Agent Framework is the recommended choice because:

- **Semantic Kernel** is essentially in maintenance mode — that team now works on Agent Framework
- **AutoGen** team also now works on Agent Framework
- You should always **pin your dependency versions** to avoid breaking changes

The GitHub Copilot SDK was declared GA earlier that week, but Agent Framework is more complex and takes longer to stabilize.

Links shared:

* [Agent Framework on PyPI](https://pypi.org/project/agent-framework/#history)

### What are the uses for observability beyond debugging and performance?

📹 [37:28](https://youtube.com/watch?v=D9vfGeoPh_I&t=2248)

Beyond debugging and performance monitoring, observability traces can be used for **quality analysis**. Once traces are exported to a log workspace (e.g., App Insights), you can:

- Pull traces back out and send them to an agent or LLM to identify low-quality responses
- Use a coding agent (like Claude Code) to analyze traces from an observability platform and find issues
- Build automated evaluations based on patterns found in production traces
- Improve prompts based on real-world failure patterns

Hamel Husain recently demonstrated this approach using Claude Code with [Arize Phoenix](https://phoenix.arize.com/) (an open-source, OpenTelemetry-based observability platform) to analyze traces and build better evaluations.

Links shared:

* [Hamel Husain's blog](https://hamel.dev/)
* [Arize Phoenix](https://phoenix.arize.com/)
* [Automating Evals with Claude Code + Phoenix](https://maven.com/p/2c8410/automating-evals-with-claude-code-phoenix)

### Should LLM-as-a-judge evaluation run in the user-facing loop or offline?

📹 [41:54](https://youtube.com/watch?v=D9vfGeoPh_I&t=2514)

LLM-as-a-judge adds too much latency for the user-facing loop. The recommended approaches are:

1. **Online/continuous evaluation**: Sample a percentage of agent calls and queue evaluations in a separate thread (not the user-facing thread), then surface results in a dashboard. If using Foundry Agents, this is [built-in with configurable sampling](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/continuous-evaluation-agents).

2. **Confidence self-reporting**: During answer generation, ask the LLM to indicate its confidence level. Display this to users per the [HAX Toolkit](https://www.microsoft.com/en-us/research/project/hax-toolkit/) guidelines for communicating AI precision.

3. **Reflection steps** (use cautiously): Pamela's team experimented with adding an LLM-based reflection step in a [RAG agentic flow](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/bonus-rag-time-journey-agentic-rag/4404652), but it added 3+ extra LLM calls and often didn't improve quality. Azure AI Search later built in a more targeted reflection step, but it's optional due to the latency cost.

The terms to search for when researching this are **"online evaluation"** and **"continuous evaluation"**.

Links shared:

* [Continuously evaluate your AI agents (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/continuous-evaluation-agents)
* [HAX Toolkit](https://www.microsoft.com/en-us/research/project/hax-toolkit/)
* [Bonus RAG-time Journey: Agentic RAG blog post](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/bonus-rag-time-journey-agentic-rag/4404652)
