import hashlib
import json

from bs4 import BeautifulSoup

from doclens.config import ROOT
from scripts.build_corpus import parse_page


def test_snapshot_rebuild_is_identical() -> None:
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    rebuilt = []
    for entry in manifest["pages"]:
        html = (ROOT / "data/raw" / f"{entry['page']}.html").read_text()
        assert hashlib.sha256(html.encode()).hexdigest() == entry["sha256"]
        chunks = parse_page(html, entry["page"])
        anchors = {tag["id"] for tag in BeautifulSoup(html, "html.parser").select("[id]")}
        for chunk in chunks:
            if "#" in chunk["url"]:
                assert chunk["url"].split("#", 1)[1] in anchors
        rebuilt.extend(chunks)
    assert rebuilt == json.loads((ROOT / "data/chunks.json").read_text())
    assert len({chunk["id"] for chunk in rebuilt}) == len(rebuilt)


def test_parser_keeps_code_spacing_and_excludes_navigation() -> None:
    html = """<nav>Unrelated navigation</nav><article class="md-content__inner">
    <h1 id="title">Title</h1><h2 id="code">Code</h2>
    <pre><span>from</span> fastapi <span>import</span> FastAPI\napp = FastAPI()</pre>
    </article>"""
    chunks = parse_page(html, "demo")
    assert chunks[0]["text"] == "from fastapi import FastAPI\napp = FastAPI()"
    assert "navigation" not in chunks[0]["text"]


def test_evaluation_set_has_both_types_and_valid_gold_pages() -> None:
    questions = json.loads((ROOT / "eval/questions.json").read_text())
    pages = {
        entry["page"] for entry in json.loads((ROOT / "data/manifest.json").read_text())["pages"]
    }
    assert len(questions) == 60
    assert len({row["id"] for row in questions}) == 60
    assert sum(row["answerable"] for row in questions) == 45
    for row in questions:
        assert set(row["gold_pages"]) <= pages
        assert bool(row["gold_pages"]) == row["answerable"]
