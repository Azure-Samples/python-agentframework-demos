<!--
---
name: Python Agent Framework Demos
description: Collection of Python examples for Microsoft Agent Framework using GitHub Models or Azure AI Foundry.
languages:
- python
products:
- azure-openai
- azure
- ai-services
page_type: sample
urlFragment: python-agentframework-demos
---
-->
# Python Agent Framework Demos

[![Open in GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/Azure-Samples/python-agentframework-demos)
[![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

This repository provides examples of [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) using LLMs from [GitHub Models](https://github.com/marketplace/models), [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/), or other model providers. GitHub Models are free to use for anyone with a GitHub account, up to a [daily rate limit](https://docs.github.com/github-models/prototyping-with-ai-models#rate-limits).

* [Getting started](#getting-started)
  * [GitHub Codespaces](#github-codespaces)
  * [VS Code Dev Containers](#vs-code-dev-containers)
  * [Local environment](#local-environment)
* [Configuring model providers](#configuring-model-providers)
  * [Using GitHub Models](#using-github-models)
  * [Using Azure AI Foundry models](#using-azure-ai-foundry-models)
  * [Using OpenAI.com models](#using-openaicom-models)
* [Running the Python examples](#running-the-python-examples)
* [Resources](#resources)

## Getting started

You have a few options for getting started with this repository.
The quickest way to get started is GitHub Codespaces, since it will setup everything for you, but you can also [set it up locally](#local-environment).

### GitHub Codespaces

You can run this repository virtually by using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the repository (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Azure-Samples/python-agentframework-demos)

2. Open a terminal window
3. Continue with the steps to run the examples

### VS Code Dev Containers

A related option is VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed)
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Continue with the steps to run the examples

### Local environment

1. Make sure the following tools are installed:

    * [Python 3.10+](https://www.python.org/downloads/)
    * Git

2. Clone the repository:

    ```shell
    git clone https://github.com/Azure-Samples/python-agentframework-demos
    cd python-agentframework-demos
    ```

3. Set up a virtual environment:

    ```shell
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

4. Install the requirements:

    ```shell
    pip install -r requirements.txt
    ```

## Configuring model providers

These examples can be run with Azure AI Foundry, OpenAI.com, or GitHub Models, depending on the environment variables you set. All the scripts reference the environment variables from a `.env` file, and an example `.env.sample` file is provided. Host-specific instructions are below.

## Using GitHub Models

If you open this repository in GitHub Codespaces, you can run the scripts for free using GitHub Models without any additional steps, as your `GITHUB_TOKEN` is already configured in the Codespaces environment.

If you want to run the scripts locally, you need to set up the `GITHUB_TOKEN` environment variable with a GitHub personal access token (PAT). You can create a PAT by following these steps:

1. Go to your GitHub account settings.
2. Click on "Developer settings" in the left sidebar.
3. Click on "Personal access tokens" in the left sidebar.
4. Click on "Tokens (classic)" or "Fine-grained tokens" depending on your preference.
5. Click on "Generate new token".
6. Give your token a name and select the scopes you want to grant. For this project, you don't need any specific scopes.
7. Click on "Generate token".
8. Copy the generated token.
9. Set the `GITHUB_TOKEN` environment variable in your terminal or IDE:

    ```shell
    export GITHUB_TOKEN=your_personal_access_token
    ```

10. Optionally, you can use a model other than "gpt-5-mini" by setting the `GITHUB_MODEL` environment variable. Use a model that supports function calling, such as: `gpt-5`, `gpt-5-mini`, `gpt-4o`, `gpt-4o-mini`, `o3-mini`, `AI21-Jamba-1.5-Large`, `AI21-Jamba-1.5-Mini`, `Codestral-2501`, `Cohere-command-r`, `Ministral-3B`, `Mistral-Large-2411`, `Mistral-Nemo`, `Mistral-small`

## Using Azure AI Foundry models

You can run all examples in this repository using GitHub Models. If you want to run the examples using models from Azure AI Foundry instead, you need to provision the Azure AI resources, which will incur costs.

This project includes infrastructure as code (IaC) to provision Azure OpenAI deployments of "gpt-5-mini" and "text-embedding-3-large" via Azure AI Foundry. The IaC is defined in the `infra` directory and uses the Azure Developer CLI to provision the resources.

1. Make sure the [Azure Developer CLI (azd)](https://aka.ms/install-azd) is installed.

2. Login to Azure:

    ```shell
    azd auth login
    ```

    For GitHub Codespaces users, if the previous command fails, try:

   ```shell
    azd auth login --use-device-code
    ```

3. Provision the OpenAI account:

    ```shell
    azd provision
    ```

    It will prompt you to provide an `azd` environment name (like "agents-demos"), select a subscription from your Azure account, and select a location. Then it will provision the resources in your account.

4. Once the resources are provisioned, you should now see a local `.env` file with all the environment variables needed to run the scripts.
5. To delete the resources, run:

    ```shell
    azd down
    ```

## Using OpenAI.com models

1. Create a `.env` file by copying the `.env.sample` file and updating it with your OpenAI API key and desired model name.

    ```bash
    cp .env.sample .env
    ```

2. Update the `.env` file with your OpenAI API key and desired model name:

    ```bash
    API_HOST=openai
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_MODEL=gpt-4o-mini
    ```

## Running the Python examples

You can run the examples in this repository by executing the scripts in the `examples` directory. Each script demonstrates a different Agent Framework pattern.

| Example | Description |
| ------- | ----------- |
| [basic.py](examples/basic.py) | Uses Agent Framework to build a basic informational agent. |
| [tool.py](examples/tool.py) | Uses Agent Framework to build an agent with a single weather tool. |
| [tools.py](examples/tools.py) | Uses Agent Framework to build a weekend planning agent with multiple tools. |
| [supervisor.py](examples/supervisor.py) | Uses Agent Framework with a supervisor orchestrating activity and recipe sub-agents. |
| [magenticone.py](examples/magenticone.py) | Uses Agent Framework to build a MagenticOne agent. |
| [hitl.py](examples/hitl.py) | Uses Agent Framework with human-in-the-loop (HITL) for tool-enabled agents with human feedback. |
| [workflow.py](examples/workflow.py) | Uses Agent Framework to build a workflow-based agent. |

## Resources

* [Agent Framework Documentation](https://learn.microsoft.com/agent-framework/)
