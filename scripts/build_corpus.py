"""Download selected official pages, or rebuild chunks from the saved HTML."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    "path-params",
    "query-params",
    "body",
    "response-model",
    "response-status-code",
    "handling-errors",
    "dependencies",
    "background-tasks",
    "middleware",
    "cors",
    "testing",
    "request-files",
]


def parse_page(html: str, page: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.md-content__inner")
    if article is None:
        raise ValueError(f"Missing documentation article in {page}")
    title_tag = article.find("h1")
    title = title_tag.get_text(" ", strip=True).replace("¶", "").strip() if title_tag else page
    section, anchor = title, ""
    paragraphs: list[str] = []
    chunks: list[dict[str, str]] = []

    def flush() -> None:
        if not paragraphs:
            return
        blocks: list[str] = []
        size = 0

        def save() -> None:
            if blocks:
                chunks.append(
                    {
                        "id": f"{page}-{len(chunks):03d}",
                        "page": page,
                        "title": title,
                        "section": section,
                        "url": f"https://fastapi.tiangolo.com/tutorial/{page}/"
                        + (f"#{anchor}" if anchor else ""),
                        "text": "\n\n".join(blocks),
                    }
                )

        for paragraph in paragraphs:
            # Split very long code examples without silently discarding their end.
            parts = [paragraph[i : i + 2200] for i in range(0, len(paragraph), 2200)]
            for part in parts:
                if size + len(part) > 2400 and blocks:
                    save()
                    blocks = blocks[-1:] if len(blocks[-1]) < 400 else []
                    size = sum(map(len, blocks))
                blocks.append(part)
                size += len(part)
        save()
        paragraphs.clear()

    for element in article.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre"]):
        if not isinstance(element, Tag):
            continue
        if element.find_parent(["pre", "li"]):
            continue
        text = (
            element.get_text("", strip=False)
            if element.name == "pre"
            else element.get_text(" ", strip=True)
        )
        text = text.replace("¶", "").strip()
        if element.name.startswith("h"):
            flush()
            section = text
            anchor = str(element.get("id", ""))
        elif text:
            paragraphs.append(text)
    flush()
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch current official pages")
    args = parser.parse_args()
    raw = ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data" / "manifest.json"
    if args.refresh:
        manifest: dict[str, object] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": "Official FastAPI tutorial (English)",
            "pages": [],
        }
        entries = []
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            for page in PAGES:
                url = f"https://fastapi.tiangolo.com/tutorial/{page}/"
                response = client.get(url)
                response.raise_for_status()
                html = response.text
                parse_page(html, page)
                (raw / f"{page}.html").write_text(html, encoding="utf-8")
                entries.append(
                    {"page": page, "url": url, "sha256": hashlib.sha256(html.encode()).hexdigest()}
                )
                print(f"Saved {page}", flush=True)
        manifest["pages"] = entries
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = []
    for entry in manifest_data["pages"]:
        html = (raw / f"{entry['page']}.html").read_text(encoding="utf-8")
        if hashlib.sha256(html.encode()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {entry['page']}")
        chunks.extend(parse_page(html, entry["page"]))
    (ROOT / "data" / "chunks.json").write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Built {len(chunks)} chunks from {len(manifest_data['pages'])} pages")


if __name__ == "__main__":
    main()
