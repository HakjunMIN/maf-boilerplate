from homestyle_ingestion.application.extraction import DomExtractionService
from homestyle_ingestion.domain.extraction import ExtractedPage


def test_extract_keeps_main_content_and_excludes_boilerplate() -> None:
    html = """
        <html>
          <body>
            <header>Header promo</header>
            <nav>Global navigation</nav>
            <main>
              <h1>신혼집 침실 스타일링</h1>
              <p>포근한 침실을 위한 핵심 제안입니다.</p>
              <div class="cookie-banner">쿠키 배너</div>
              <section>
                <h2>추천 포인트</h2>
                <p>원목 침대와 조명을 함께 배치합니다.</p>
              </section>
            </main>
            <footer>Footer links</footer>
          </body>
        </html>
    """

    extracted_page = DomExtractionService().extract(
        url="https://homestyle.lge.co.kr/home",
        html=html,
    )

    assert extracted_page == ExtractedPage(
        url="https://homestyle.lge.co.kr/home",
        title="신혼집 침실 스타일링",
        breadcrumb=(),
        markdown="# 신혼집 침실 스타일링\n\n포근한 침실을 위한 핵심 제안입니다.\n\n## 추천 포인트\n\n원목 침대와 조명을 함께 배치합니다.",
    )


def test_extract_reads_breadcrumb_from_dom() -> None:
    html = """
        <html>
          <body>
            <nav aria-label="breadcrumb">
              <a href="/home">홈</a>
              <a href="/collection">컬렉션</a>
              <span>침실</span>
            </nav>
            <main>
              <h1>침실 컬렉션</h1>
              <p>침실 스타일 제안입니다.</p>
            </main>
          </body>
        </html>
    """

    extracted_page = DomExtractionService().extract(
        url="https://homestyle.lge.co.kr/collection/bedroom",
        html=html,
    )

    assert extracted_page.breadcrumb == ("홈", "컬렉션", "침실")


def test_extract_falls_back_to_url_path_when_breadcrumb_is_missing() -> None:
    html = """
        <html>
          <body>
            <main>
              <h1>브랜드 스토리</h1>
              <p>브랜드 소개 콘텐츠입니다.</p>
            </main>
          </body>
        </html>
    """

    extracted_page = DomExtractionService().extract(
        url="https://homestyle.lge.co.kr/brand/story",
        html=html,
    )

    assert extracted_page.breadcrumb == ("brand", "story")


def test_extract_keeps_price_promotion_and_table_content_from_html() -> None:
    html = """
        <html>
          <body>
            <main>
              <h1>오브제컬렉션 냉장고</h1>
              <div class="hero-price">3,290,000원</div>
              <div class="promo-banner">카드 결제 시 7% 할인</div>
              <section>
                <h2>구매 혜택</h2>
                <ul>
                  <li>무이자 12개월</li>
                  <li>설치비 무료</li>
                </ul>
                <table>
                  <tr><th>용량</th><td>610L</td></tr>
                  <tr><th>색상</th><td>베이지 / 실버</td></tr>
                </table>
              </section>
              <div aria-hidden="true">숨김 배너</div>
            </main>
          </body>
        </html>
    """

    extracted_page = DomExtractionService().extract(
        url="https://homestyle.lge.co.kr/item?productId=G123",
        html=html,
    )

    assert extracted_page.markdown == (
        "# 오브제컬렉션 냉장고\n\n"
        "3,290,000원\n\n"
        "카드 결제 시 7% 할인\n\n"
        "## 구매 혜택\n\n"
      "- 무이자 12개월\n\n"
      "- 설치비 무료\n\n"
        "용량 | 610L\n\n"
        "색상 | 베이지 / 실버"
    )
