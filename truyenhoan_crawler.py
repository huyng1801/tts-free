import re
import time
from urllib.parse import quote, urljoin, urlparse

import cloudscraper
from bs4 import BeautifulSoup

BASE = "https://truyenhoan.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",
}

_session = None
_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 300


def _get_session():
    global _session
    if _session is None:
        _session = cloudscraper.create_scraper()
    return _session


def _cached(key: str):
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
        del _cache[key]
    return None


def _store_cache(key: str, val: object) -> None:
    _cache[key] = (time.time(), val)


def fetch_html(url: str) -> str:
    session = _get_session()
    resp = session.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = urljoin(BASE + "/", url.lstrip("/"))
    parsed = urlparse(url)
    if "truyenhoan.com" not in parsed.netloc:
        raise ValueError("Chỉ hỗ trợ link từ truyenhoan.com")
    return url


def _story_url_key(url: str) -> str:
    url = _normalize_url(url).rstrip("/") + "/"
    return url


def parse_story_url(url: str) -> dict:
    url = _story_url_key(url)
    m = re.search(r"truyenhoan\.com/([a-z0-9-]+)\.(\d+)/?", url)
    if not m:
        raise ValueError("Link truyện không hợp lệ")
    return {"slug": m.group(1), "story_id": m.group(2), "url": url}


def parse_chapter_url(url: str) -> dict:
    url = _normalize_url(url)
    m = re.search(r"truyenhoan\.com/([a-z0-9-]+)/chuong-(\d+)\.html", url)
    if not m:
        raise ValueError("Link chương không hợp lệ")
    return {
        "slug": m.group(1),
        "chapter": int(m.group(2)),
        "url": url,
    }


def search_stories(query: str, limit: int = 20) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    cache_key = f"search:{query.lower()}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached[:limit]

    url = f"{BASE}/tim-kiem/?q={quote(query)}"
    soup = BeautifulSoup(fetch_html(url), "html.parser")
    results: list[dict] = []
    seen: set[str] = set()

    for a in soup.select("h3 a[href]"):
        href = a.get("href", "")
        if not re.search(r"truyenhoan\.com/[a-z0-9-]+\.\d+/?$", href):
            continue
        if href in seen:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        seen.add(href)
        results.append({"title": title, "url": href.rstrip("/") + "/"})

    _store_cache(cache_key, results)
    return results[:limit]


def _extract_chapters_from_soup(soup: BeautifulSoup, slug: str) -> list[dict]:
    chapters: dict[int, dict] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(rf"{re.escape(slug)}/chuong-(\d+)\.html", href)
        if not m:
            continue
        num = int(m.group(1))
        title = a.get_text(strip=True) or f"Chương {num}"
        title = re.sub(r"\s+", " ", title)
        if num not in chapters or len(title) > len(chapters[num]["title"]):
            chapters[num] = {
                "number": num,
                "title": title,
                "url": href if href.startswith("http") else urljoin(BASE, href),
            }
    return sorted(chapters.values(), key=lambda x: x["number"], reverse=True)


def _last_chapter_page(soup: BeautifulSoup) -> int:
    last = 1
    for a in soup.select(".pagination a, a.page-numbers"):
        href = a.get("href", "")
        m = re.search(r"/trang-(\d+)/", href)
        if m:
            last = max(last, int(m.group(1)))
        text = a.get_text(strip=True)
        if text.isdigit():
            last = max(last, int(text))
    return last


def get_story(story_url: str) -> dict:
    story_url = _story_url_key(story_url)
    cache_key = f"story:{story_url}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    meta = parse_story_url(story_url)
    soup = BeautifulSoup(fetch_html(story_url), "html.parser")
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else meta["slug"]

    author = ""
    author_el = soup.select_one(".author, .info a, .story-info a")
    if author_el:
        author = author_el.get_text(strip=True)

    total_pages = _last_chapter_page(soup)
    chapters = _extract_chapters_from_soup(soup, meta["slug"])

    for page in range(2, total_pages + 1):
        page_url = f"{story_url}trang-{page}/#chapter-list"
        page_soup = BeautifulSoup(fetch_html(page_url), "html.parser")
        chapters.extend(_extract_chapters_from_soup(page_soup, meta["slug"]))

    by_num = {c["number"]: c for c in chapters}
    chapters = sorted(by_num.values(), key=lambda x: x["number"], reverse=True)

    result = {
        "title": title,
        "slug": meta["slug"],
        "story_id": meta["story_id"],
        "url": story_url,
        "author": author,
        "chapter_count": len(chapters),
        "max_chapter": max((c["number"] for c in chapters), default=0),
        "chapters": chapters,
    }
    _store_cache(cache_key, result)
    return result


def clean_chapter_text(element) -> str:
    for tag in element.find_all(["script", "style", "ins", "iframe"]):
        tag.decompose()
    for br in element.find_all("br"):
        br.replace_with("\n")
    text = element.get_text("\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    for marker in (
        "Bạn đang đọc truyện trên",
        "Báo lỗi chương",
        "truyện ngôn tình full",
        "Website hoạt động dưới",
    ):
        if marker in text:
            text = text.split(marker)[0]

    return text.strip()


def get_chapter(chapter_url: str | None = None, slug: str | None = None, number: int | None = None) -> dict:
    if chapter_url:
        meta = parse_chapter_url(_normalize_url(chapter_url))
        url = meta["url"]
        slug = meta["slug"]
        number = meta["chapter"]
    elif slug and number:
        url = f"{BASE}/{slug}/chuong-{number}.html"
    else:
        raise ValueError("Cần link chương hoặc slug + số chương")

    cache_key = f"chapter:{url}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    soup = BeautifulSoup(fetch_html(url), "html.parser")
    content_el = soup.select_one(".chapter-c, #chapter-c")
    if not content_el:
        raise ValueError("Không tìm thấy nội dung chương")

    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else f"Chương {number}"
    text = clean_chapter_text(content_el)
    if not text:
        raise ValueError("Chương trống")

    story_link = soup.select_one(f"a[href*='{slug}.']")
    story_url = story_link["href"] if story_link else None
    if story_url and not story_url.startswith("http"):
        story_url = urljoin(BASE, story_url)

    result = {
        "title": title,
        "slug": slug,
        "number": number,
        "url": url,
        "story_url": story_url,
        "text": text,
        "char_count": len(text),
    }
    _store_cache(cache_key, result)
    return result


def resolve_input(value: str) -> dict:
    value = value.strip()
    if not value:
        raise ValueError("Vui lòng nhập link hoặc tên truyện")

    if "truyenhoan.com" in value and "chuong-" in value:
        return {"type": "chapter", **get_chapter(chapter_url=value)}
    if "truyenhoan.com" in value and re.search(r"\.\d+/?$", value):
        return {"type": "story", **get_story(value)}
    return {"type": "search", "results": search_stories(value)}
