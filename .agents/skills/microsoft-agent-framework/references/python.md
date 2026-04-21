# Microsoft Agent Framework for Python

Use this reference when the target project is written in Python.

## Authoritative sources

- Repository: <https://github.com/microsoft/agent-framework/tree/main/python>
- Samples: <https://github.com/microsoft/agent-framework/tree/main/python/samples>

## Installation

For new projects, install the package with:

```bash
pip install agent-framework
```

## Python-specific guidance

- Use modern async patterns throughout agent and workflow operations.
- Add type hints and keep APIs explicit even in dynamic code.
- Follow standard Python packaging and environment practices for dependencies and tooling.
- For Azure-backed clients such as Azure OpenAI or Azure AI Foundry, use `DefaultAzureCredential` as the default authentication mechanism.
- Do not use API keys for Azure-backed Python MAF integrations unless the user explicitly asks for an API-key-based setup.
- Prefer Azure OpenAI by default for new Azure-backed Python MAF projects unless the user explicitly requires Azure AI Foundry or another provider.
- Prefer managed identity in deployed environments and `az login`-backed local development over secrets in `.env` files.
- Use middleware, context providers, and orchestration patterns in ways that fit the Python application structure.
- Check the latest Python samples before introducing new APIs or workflow patterns.
