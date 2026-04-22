from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from agent_framework._agents import Agent
from agent_framework._clients import SupportsChatGetResponse
from agent_framework._tools import tool


@dataclass(frozen=True)
class WebSearchResult:
    summary: str
    results: list[str]


class WebSearchAgent:
    def __init__(self, client: SupportsChatGetResponse[Any], max_results: int = 5) -> None:
        self._client = client
        self._max_results = max_results
        self._agent = Agent[Any](
            name="web_search_agent",
            instructions=(
                "You are a web research agent. "
                "Use search_duckduckgo exactly once when you need external information and return a concise summary."
            ),
            client=self._client,
        )

    async def run(self, query: str) -> WebSearchResult:
        captured_results: list[str] = []

        @tool
        async def search_duckduckgo(search_query: str) -> list[str]:
            """Search the public web with DuckDuckGo and return text snippets only."""
            results = await self._search(search_query)
            captured_results.extend(results)
            return results

        response = await self._agent.run(
            f"Research this request using public web search: {query}.",
            tools=[search_duckduckgo],
        )
        return WebSearchResult(summary=response.text.strip(), results=captured_results)

    async def _search(self, query: str) -> list[str]:
        def _run() -> list[str]:
            from duckduckgo_search import DDGS

            results = list(DDGS().text(query, max_results=self._max_results))
            snippets: list[str] = []
            for result in results:
                body = (result.get("body") or "").strip()
                href = (result.get("href") or "").strip()
                title = (result.get("title") or "").strip()
                parts = [part for part in (title, body, href) if part]
                if parts:
                    snippets.append(" - ".join(parts))
            return snippets

        return await asyncio.to_thread(_run)