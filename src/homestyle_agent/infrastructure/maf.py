import importlib.metadata
from typing import Any

from azure.core.credentials import TokenCredential

from homestyle_shared.domain.indexing import SectionDocument

_GROUNDING_INSTRUCTIONS = """당신은 LG 홈스타일 콘텐츠 질의응답 에이전트입니다.
반드시 제공된 Grounding Context 안의 정보만 사용해 한국어로 답변하세요.
근거가 없는 내용은 추측하지 말고, 본문 답변만 작성하세요.
citation, footnote, 참고 링크는 쓰지 마세요.
답변은 3~5문장으로 간결하게 작성하세요."""


class MafGroundedBodyGenerator:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        credential: TokenCredential,
        api_version: str,
    ) -> None:
        _patch_agent_framework_version()
        from agent_framework._agents import Agent
        from agent_framework_openai import OpenAIChatClient

        self._agent: Any = Agent(
            client=OpenAIChatClient(
                model=model,
                azure_endpoint=endpoint,
                credential=credential,
                api_version=api_version,
            ),
            instructions=_GROUNDING_INSTRUCTIONS,
            name="HomestyleGroundedAgent",
        )

    async def generate_grounded_body(
        self,
        question: str,
        sections: list[SectionDocument],
    ) -> str:
        result = await self._agent.run(self._build_prompt(question, sections))
        return str(result).strip()

    def _build_prompt(self, question: str, sections: list[SectionDocument]) -> str:
        context = "\n\n".join(
            (
                f"[{index}] URL: {section.page_url}\n"
                f"제목: {section.title}\n"
                f"섹션: {section.section_heading}\n"
                f"본문: {section.content}"
            )
            for index, section in enumerate(sections, start=1)
        )
        return (
            "질문에 답할 때 아래 Grounding Context만 사용하세요.\n\n"
            f"질문:\n{question}\n\n"
            f"Grounding Context:\n{context}"
        )


def _patch_agent_framework_version() -> None:
    import agent_framework

    if getattr(agent_framework, "__version__", None):
        return
    agent_framework.__version__ = importlib.metadata.version("agent-framework")
