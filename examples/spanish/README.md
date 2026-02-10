<!--
---
name: Python Agent Framework Demos
description: Colección de ejemplos en Python para Microsoft Agent Framework usando GitHub Models o Azure AI Foundry.
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

# Demos de Microsoft Agent Framework en Python

[![Abrir en GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/Azure-Samples/python-agentframework-demos)
[![Abrir en Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

Este repositorio ofrece ejemplos de [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) usando LLMs de [GitHub Models](https://github.com/marketplace/models), [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/) u otros proveedores de modelos. Los modelos de GitHub son gratuitos para cualquiera con una cuenta de GitHub, hasta un [límite diario](https://docs.github.com/github-models/prototyping-with-ai-models#rate-limits).

* [Cómo empezar](#cómo-empezar)
  * [GitHub Codespaces](#github-codespaces)
  * [VS Code Dev Containers](#vs-code-dev-containers)
  * [Entorno local](#entorno-local)
* [Configurar proveedores de modelos](#configurar-proveedores-de-modelos)
  * [Usar GitHub Models](#usar-github-models)
  * [Usar modelos de Azure AI Foundry](#usar-modelos-de-azure-ai-foundry)
  * [Usar modelos de OpenAI.com](#usar-modelos-de-openaicom)
* [Ejecutar los ejemplos en Python](#ejecutar-los-ejemplos-en-python)
* [Recursos](#recursos)

## Cómo empezar

Tienes varias opciones para comenzar con este repositorio.
La forma más rápida es usar GitHub Codespaces, ya que te deja todo listo automáticamente, pero también puedes [configurarlo localmente](#entorno-local).

### GitHub Codespaces

Puedes ejecutar este repositorio virtualmente usando GitHub Codespaces. El botón abrirá una instancia de VS Code basada en web en tu navegador:

1. Abre el repositorio (esto puede tardar varios minutos):

    [![Abrir en GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Azure-Samples/python-agentframework-demos)

2. Abre una ventana de terminal
3. Continúa con los pasos para ejecutar los ejemplos

### VS Code Dev Containers

Una opción relacionada es VS Code Dev Containers, que abrirá el proyecto en tu VS Code local usando la [extensión Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Inicia Docker Desktop (instálalo si no lo tienes ya)
2. Abre el proyecto:

    [![Abrir en Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/python-agentframework-demos)

3. En la ventana de VS Code que se abre, una vez que aparezcan los archivos del proyecto (esto puede tardar varios minutos), abre una ventana de terminal.
4. Continúa con los pasos para ejecutar los ejemplos

### Entorno local

1. Asegúrate de tener instaladas las siguientes herramientas:

    * [Python 3.10+](https://www.python.org/downloads/)
    * Git

2. Clona el repositorio:

    ```shell
    git clone https://github.com/Azure-Samples/python-agentframework-demos
    cd python-agentframework-demos
    ```

3. Configura un entorno virtual:

    ```shell
    python -m venv .venv
    source .venv/bin/activate  # En Windows: .venv\Scripts\activate
    ```

4. Instala los requisitos:

    ```shell
    pip install -r requirements.txt
    ```

## Configurar proveedores de modelos

Estos ejemplos se pueden ejecutar con Azure AI Foundry, OpenAI.com o GitHub Models, dependiendo de las variables de entorno que configures. Todos los scripts hacen referencia a las variables de entorno de un archivo `.env`, y se proporciona un archivo de ejemplo `.env.sample`. Las instrucciones específicas de cada proveedor se encuentran a continuación.

## Usar GitHub Models

Si abres este repositorio en GitHub Codespaces, puedes ejecutar los scripts gratis usando GitHub Models sin pasos adicionales, ya que tu `GITHUB_TOKEN` ya está configurado en el entorno de Codespaces.

Si quieres ejecutar los scripts localmente, necesitas configurar la variable de entorno `GITHUB_TOKEN` con un token de acceso personal (PAT) de GitHub. Puedes crear un PAT siguiendo estos pasos:

1. Ve a la configuración de tu cuenta de GitHub.
2. Haz clic en "Developer settings" en la barra lateral izquierda.
3. Haz clic en "Personal access tokens" en la barra lateral izquierda.
4. Haz clic en "Tokens (classic)" o "Fine-grained tokens" según tu preferencia.
5. Haz clic en "Generate new token".
6. Ponle un nombre a tu token y selecciona los alcances que quieres otorgar. Para este proyecto, no necesitas alcances específicos.
7. Haz clic en "Generate token".
8. Copia el token generado.
9. Configura la variable de entorno `GITHUB_TOKEN` en tu terminal o IDE:

    ```shell
    export GITHUB_TOKEN=tu_token_de_acceso_personal
    ```

10. Opcionalmente, puedes usar un modelo diferente a "gpt-5-mini" configurando la variable de entorno `GITHUB_MODEL`. Usa un modelo que soporte llamadas de funciones, como: `gpt-5`, `gpt-5-mini`, `gpt-4o`, `gpt-4o-mini`, `o3-mini`, `AI21-Jamba-1.5-Large`, `AI21-Jamba-1.5-Mini`, `Codestral-2501`, `Cohere-command-r`, `Ministral-3B`, `Mistral-Large-2411`, `Mistral-Nemo`, `Mistral-small`

## Usar modelos de Azure AI Foundry

Puedes ejecutar todos los ejemplos en este repositorio usando GitHub Models. Si quieres ejecutar los ejemplos usando modelos de Azure AI Foundry, necesitas provisionar los recursos de Azure AI, lo que generará costos.

Este proyecto incluye infraestructura como código (IaC) para provisionar despliegues de Azure OpenAI de "gpt-5-mini" y "text-embedding-3-large" a través de Azure AI Foundry. La IaC está definida en el directorio `infra` y usa Azure Developer CLI para provisionar los recursos.

1. Asegúrate de tener instalado [Azure Developer CLI (azd)](https://aka.ms/install-azd).

2. Inicia sesión en Azure:

    ```shell
    azd auth login
    ```

    Para usuarios de GitHub Codespaces, si el comando anterior falla, prueba:

   ```shell
    azd auth login --use-device-code
    ```

3. Provisiona la cuenta de OpenAI:

    ```shell
    azd provision
    ```

    Te pedirá que proporciones un nombre de entorno `azd` (como "agents-demos"), selecciones una suscripción de tu cuenta de Azure y selecciones una ubicación. Luego aprovisionará los recursos en tu cuenta.

4. Una vez que los recursos estén aprovisionados, deberías ver un archivo local `.env` con todas las variables de entorno necesarias para ejecutar los scripts.
5. Para eliminar los recursos, ejecuta:

    ```shell
    azd down
    ```

## Usar modelos de OpenAI.com

1. Crea un archivo `.env` copiando el archivo `.env.sample` y actualizándolo con tu clave API de OpenAI y el nombre del modelo deseado.

    ```bash
    cp .env.sample .env
    ```

2. Actualiza el archivo `.env` con tu clave API de OpenAI y el nombre del modelo deseado:

    ```bash
    API_HOST=openai
    OPENAI_API_KEY=tu_clave_api_de_openai
    OPENAI_MODEL=gpt-4o-mini
    ```

## Ejecutar los ejemplos en Python

Puedes ejecutar los ejemplos en este repositorio ejecutando los scripts en el directorio `examples/spanish`. Cada script demuestra un patrón diferente de Microsoft Agent Framework.

| Ejemplo | Descripción |
| ------- | ----------- |
| [agent_basic.py](agent_basic.py) | Usa Agent Framework para crear un agente informativo básico. |
| [agent_tool.py](agent_tool.py) | Usa Agent Framework para crear un agente con una única herramienta de clima. |
| [agent_tools.py](agent_tools.py) | Usa Agent Framework para crear un agente planificador de fin de semana con múltiples herramientas. |
| [agent_supervisor.py](agent_supervisor.py) | Usa Agent Framework con un supervisor que orquesta subagentes de actividades y recetas. |
| [workflow_magenticone.py](workflow_magenticone.py) | Usa Agent Framework para crear un flujo de trabajo multi-agente MagenticOne. |
| [workflow_hitl.py](workflow_hitl.py) | Usa Agent Framework con human-in-the-loop (HITL) para confirmar o editar respuestas. |
| [agent_middleware.py](agent_middleware.py) | Usa Agent Framework con middleware de agente, chat y funciones para registro, temporización y bloqueo. |
| [agent_mcp_remote.py](agent_mcp_remote.py) | Un agente que usa un servidor MCP remoto (Microsoft Learn) para búsqueda de documentación. |
| [agent_mcp_local.py](agent_mcp_local.py) | Un agente conectado a un servidor MCP local (ej. para registro de gastos). |
| [openai_tool_calling.py](openai_tool_calling.py) | Llamadas a funciones con el SDK de OpenAI de bajo nivel, mostrando despacho manual de herramientas. |
| [workflow_basic.py](workflow_basic.py) | Usa Agent Framework para crear un agente basado en flujo de trabajo. |

## Recursos

* [Documentación de Agent Framework](https://learn.microsoft.com/agent-framework/)
