from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from doclens.app import create_app
from doclens.config import ROOT, Settings
from doclens.rag import Assistant, ModelAnswer, OllamaClient, OllamaError
from doclens.retrieval import Chunk, Hit, SearchIndex


class FakeOllama(OllamaClient):
    def __init__(self, answer: ModelAnswer | None = None, fail: bool = False) -> None:
        super().__init__(Settings())
        self.response = answer or ModelAnswer(
            can_answer=True,
            answer="Raise HTTPException with status_code=404. [S1]",
            citation_ids=["S1"],
        )
        self.fail = fail
        self.calls = 0

    def generate(self, question: str, hits: list[Hit]) -> ModelAnswer:
        self.calls += 1
        if self.fail:
            raise OllamaError("Local model is unavailable")
        return self.response


@pytest.fixture
def index() -> SearchIndex:
    return SearchIndex.load(ROOT / "data" / "chunks.json")


@pytest.fixture
def settings() -> Settings:
    return Settings()


def test_retrieval_finds_error_documentation(index: SearchIndex) -> None:
    hits = index.search("How do I raise HTTPException with a 404 status?")
    assert hits[0].chunk.page == "handling-errors"
    assert "404" in hits[0].chunk.text


def test_unknown_words_produce_no_results(index: SearchIndex) -> None:
    assert index.search("zxqvkjxyz") == []


def test_retrieval_ties_are_stable() -> None:
    chunks = [
        Chunk(key, "p", "Title", "Section", "https://example.org", "same terms")
        for key in ["b", "a"]
    ]
    index = SearchIndex(chunks)
    assert [hit.chunk.id for hit in index.search("same")] == ["a", "b"]


def test_no_evidence_skips_model(index: SearchIndex, settings: Settings) -> None:
    client = FakeOllama()
    answer = Assistant(index, settings, client).answer("zxqvkjxyz")
    assert answer.status == "abstained"
    assert answer.citations == []
    assert client.calls == 0


def test_model_refusal_is_preserved(index: SearchIndex, settings: Settings) -> None:
    client = FakeOllama(ModelAnswer(can_answer=False, answer="", citation_ids=[]))
    answer = Assistant(index, settings, client).answer("How do I raise HTTPException?")
    assert answer.status == "abstained"
    assert answer.citations == []


def test_uncovered_topic_skips_model(index: SearchIndex, settings: Settings) -> None:
    client = FakeOllama()
    answer = Assistant(index, settings, client).answer(
        "How do I configure Kubernetes autoscaling for a FastAPI deployment?"
    )
    assert answer.status == "abstained"
    assert client.calls == 0


def test_unused_declared_sources_are_not_shown(index: SearchIndex, settings: Settings) -> None:
    client = FakeOllama(
        ModelAnswer(can_answer=True, answer="Raise HTTPException. [S1]", citation_ids=["S1", "S2"])
    )
    answer = Assistant(index, settings, client).answer("How do I raise HTTPException?")
    assert answer.status == "answered"
    assert [source["label"] for source in answer.citations] == ["S1"]


@pytest.mark.parametrize(
    "text,ids",
    [
        ("An invented API. [S99]", ["S99"]),
        ("An unsupported answer.", ["S1"]),
        ("An answer. [S1]", ["S2"]),
        ("Read https://evil.example. [S1]", ["S1"]),
    ],
)
def test_invalid_sources_are_rejected(
    index: SearchIndex, settings: Settings, text: str, ids: list[str]
) -> None:
    client = FakeOllama(ModelAnswer(can_answer=True, answer=text, citation_ids=ids))
    answer = Assistant(index, settings, client).answer("How do I raise HTTPException?")
    assert answer.status == "abstained"
    assert answer.citations == []


def test_urls_are_resolved_from_corpus(index: SearchIndex, settings: Settings) -> None:
    answer = Assistant(index, settings, FakeOllama()).answer("HTTPException 404")
    assert answer.status == "answered"
    assert answer.citations[0]["url"].startswith(
        "https://fastapi.tiangolo.com/tutorial/handling-errors/"
    )


def test_search_works_when_model_is_unavailable(index: SearchIndex, settings: Settings) -> None:
    assistant = Assistant(index, settings, FakeOllama(fail=True))
    with TestClient(create_app(settings, assistant)) as client:
        response = client.post("/api/ask", json={"question": "HTTPException", "mode": "search"})
        assert response.status_code == 200
        assert response.json()["retrieved"]
        failed = client.post("/api/ask", json={"question": "HTTPException"})
        assert failed.status_code == 503
        assert "unavailable" in failed.json()["detail"]


@pytest.mark.parametrize("question", ["", "   ", "x" * 601])
def test_invalid_questions_are_rejected(
    index: SearchIndex, settings: Settings, question: str
) -> None:
    with TestClient(create_app(settings, Assistant(index, settings, FakeOllama()))) as client:
        assert client.post("/api/ask", json={"question": question}).status_code == 422


def test_home_and_api_metadata(index: SearchIndex, settings: Settings) -> None:
    with TestClient(create_app(settings, Assistant(index, settings, FakeOllama()))) as client:
        assert client.get("/").status_code == 200
        assert "document-search-rag" in client.get("/").text
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/info").json()["pages"] == 12
        assert "/api/ask" in client.get("/openapi.json").json()["paths"]


def test_ollama_timeout_becomes_service_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "post", timeout)
    with pytest.raises(OllamaError):
        OllamaClient(Settings()).generate("HTTPException?", [])


def test_config_rejects_remote_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCLENS_OLLAMA_URL", "https://example.org")
    with pytest.raises(ValueError, match="local"):
        Settings.from_env()


def test_corpus_missing_gives_actionable_error(tmp_path: Path) -> None:
    empty = tmp_path / "chunks.json"
    empty.write_text("[]")
    with pytest.raises(ValueError, match="Corpus is empty"):
        SearchIndex.load(empty)


@pytest.mark.live
def test_live_answer_and_unanswerable(index: SearchIndex, settings: Settings) -> None:
    assistant = Assistant(index, settings, OllamaClient(settings))
    answer = assistant.answer("How do I raise HTTPException with a 404 status?")
    assert answer.status == "answered"
    assert "404" in answer.answer
    assert answer.citations
    refusal = assistant.answer("What is the capital of France?")
    assert refusal.status == "abstained"
