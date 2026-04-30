from pathlib import Path

import pytest

from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.fetch import FetchMetadata
from homestyle_ingestion.infrastructure.storage import (
    LocalPageStore,
    PageStoreNotFoundError,
    StoredPage,
    StoredPageInventoryEntry,
)


@pytest.mark.asyncio
async def test_local_page_store_saves_and_loads_page_markdown_with_fetch_metadata(
    tmp_path: Path,
) -> None:
    store = LocalPageStore(root_directory=tmp_path)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n렌더된 본문입니다.",
    )
    metadata = FetchMetadata(
        url=page.url,
        etag='"etag-1"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
    )

    await store.save_page(page, metadata, "v2")
    stored_page = await store.load_page(page.url)

    assert stored_page == StoredPage(
        page=page,
        metadata=metadata,
        extraction_version="v2",
    )


@pytest.mark.asyncio
async def test_local_page_store_reuses_stable_file_key_for_same_url(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path)
    url = "https://homestyle.lge.co.kr/collection/living-room"

    await store.save_page(
        ExtractedPage(
            url=url,
            title="첫 번째",
            breadcrumb=("collection", "living-room"),
            markdown="# 첫 번째",
        ),
        FetchMetadata(
            url=url,
            etag='"etag-1"',
            last_modified=None,
            content_hash="hash-1",
        ),
        "v1",
    )
    await store.save_page(
        ExtractedPage(
            url=url,
            title="두 번째",
            breadcrumb=("collection", "living-room"),
            markdown="# 두 번째",
        ),
        FetchMetadata(
            url=url,
            etag='"etag-2"',
            last_modified=None,
            content_hash="hash-2",
        ),
        "v2",
    )

    stored_files = sorted(tmp_path.glob("*.json"))

    assert len(stored_files) == 1
    assert stored_files[0].stem
    assert await store.load_page(url) == StoredPage(
        page=ExtractedPage(
            url=url,
            title="두 번째",
            breadcrumb=("collection", "living-room"),
            markdown="# 두 번째",
        ),
        metadata=FetchMetadata(
            url=url,
            etag='"etag-2"',
            last_modified=None,
            content_hash="hash-2",
        ),
        extraction_version="v2",
    )


@pytest.mark.asyncio
async def test_local_page_store_raises_explicit_error_for_missing_url(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path)
    missing_url = "https://homestyle.lge.co.kr/collection/missing-page"

    with pytest.raises(PageStoreNotFoundError, match=missing_url):
        await store.load_page(missing_url)


@pytest.mark.asyncio
async def test_local_page_store_preserves_page_segments_for_vlm_provenance(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n짧은 본문",
        segments=(
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#dom-1",
                markdown="# 거실 컬렉션\n\n짧은 본문",
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                markdown="## 이미지 설명\n\n패브릭 소파 조합입니다.",
                source_kind="vlm",
                confidence_score=0.82,
                review_state="not_required",
                is_image_derived=True,
            ),
        ),
    )
    metadata = FetchMetadata(
        url=page.url,
        etag='"etag-1"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
    )

    await store.save_page(page, metadata, "v2")

    assert await store.load_page(page.url) == StoredPage(
        page=page,
        metadata=metadata,
        extraction_version="v2",
    )


@pytest.mark.asyncio
async def test_local_page_store_persists_delete_tombstones_in_inventory(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path)
    url = "https://homestyle.lge.co.kr/collection/living-room"
    metadata = FetchMetadata(
        url=url,
        etag='"etag-1"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
    )

    await store.save_page(
        ExtractedPage(
            url=url,
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            markdown="# 거실 컬렉션",
        ),
        metadata,
        "v2",
    )
    await store.mark_deleted(url, "2026-04-28T00:00:00+00:00")

    assert await store.list_pages() == [
        StoredPageInventoryEntry(
            url=url,
            metadata=metadata,
            extraction_version="v2",
            is_deleted=True,
            deleted_at="2026-04-28T00:00:00+00:00",
        )
    ]

    await store.save_page(
        ExtractedPage(
            url=url,
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            markdown="# 거실 컬렉션\n\n재수집됨",
        ),
        metadata,
        "v3",
    )

    assert await store.list_pages() == [
        StoredPageInventoryEntry(
            url=url,
            metadata=metadata,
            extraction_version="v3",
        )
    ]
