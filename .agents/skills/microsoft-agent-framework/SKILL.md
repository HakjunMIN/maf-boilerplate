---
name: microsoft-agent-framework
description: 'Create, update, refactor, explain, or review Microsoft Agent Framework solutions for Python.'
---

# Microsoft Agent Framework

Use this skill when working with applications, agents, workflows, or migrations built on Microsoft Agent Framework.

Microsoft Agent Framework is the unified successor to Semantic Kernel and AutoGen, combining their strengths with new capabilities. Because it is still in public preview and changes quickly, always ground implementation advice in the latest official documentation and samples rather than relying on stale knowledge.

## Scope

This skill is Python-only.

- Use this skill when the repository contains `.py`, `pyproject.toml`, or `requirements.txt`, or when the user explicitly asks for Python guidance.
- Do not use this skill as a source of non-Python implementation guidance.
- Follow [references/python.md](references/python.md) for language-specific guidance.

## Always consult live documentation

- Read the Microsoft Agent Framework overview first: <https://learn.microsoft.com/agent-framework/overview/agent-framework-overview>
- Prefer official docs and samples for the current API surface.
- Use the Microsoft Docs MCP tooling when available to fetch up-to-date framework guidance and examples.
- Treat older Semantic Kernel or AutoGen patterns as migration inputs, not as the default implementation model.

## Shared guidance

When working with Microsoft Agent Framework in any language:

- Use async patterns for agent and workflow operations.
- Implement explicit error handling and logging.
- Prefer strong typing, clear interfaces, and maintainable composition patterns.
- For Azure-hosted model providers and services, default to keyless authentication with `DefaultAzureCredential`.
- Do not recommend or generate API-key-based authentication for Azure AI Foundry, Azure OpenAI, or other Azure-backed MAF integrations unless the user explicitly requires it.
- Treat managed identity, local `az login`, and workload identity flows as the standard authentication path for Azure-backed MAF solutions.
- Use agents for autonomous decision-making, ad hoc planning, conversation flows, tool usage, and MCP server interactions.
- Use workflows for multi-step orchestration, predefined execution graphs, long-running tasks, and human-in-the-loop scenarios.
- Support model providers such as Azure OpenAI, Azure AI Foundry, OpenAI, and others, but prefer Azure OpenAI for new Azure-backed MAF projects unless the user asks for a different provider.
- Use thread-based or equivalent state handling, context providers, middleware, checkpointing, routing, and orchestration patterns when they fit the problem.

## Workflow

1. Confirm the task is for Python.
2. Fetch the latest official docs and Python samples before making implementation choices.
3. Apply the shared agent and workflow guidance from this skill.
4. Use the Python package, repository path, sample paths, and coding practices from the Python reference.
5. When examples in the repo differ from current docs, explain the difference and follow the current supported pattern.

## References

- [Python reference](references/python.md)

## Completion criteria

- Recommendations target Python only.
- Package names, repository paths, and sample locations match the Python ecosystem.
- Guidance reflects current Microsoft Agent Framework documentation rather than legacy assumptions.
- Migration advice calls out Semantic Kernel and AutoGen only when relevant.
