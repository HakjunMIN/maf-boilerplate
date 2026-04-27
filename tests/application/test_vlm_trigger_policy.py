from homestyle_ingestion.application.vlm import VlmTriggerPolicy
from homestyle_ingestion.domain.vlm import ExtractedBlock, ImageCandidate


def test_should_extract_when_block_has_short_text_and_meaningful_image() -> None:
    policy = VlmTriggerPolicy()
    block = ExtractedBlock(
        text="침실 분위기를 설명하는 짧은 배너 문구",
        images=(
            ImageCandidate(width=320, role=None, aria_hidden=False),
        ),
    )

    assert policy.should_extract(block) is True


def test_should_not_extract_for_decorative_images() -> None:
    policy = VlmTriggerPolicy()
    block = ExtractedBlock(
        text="짧은 문구",
        images=(
            ImageCandidate(width=80, role=None, aria_hidden=False),
            ImageCandidate(width=240, role="presentation", aria_hidden=False),
            ImageCandidate(width=320, role=None, aria_hidden=True),
        ),
    )

    assert policy.should_extract(block) is False
