from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from doclens.config import Settings
from doclens.rag import Answer, Assistant, OllamaClient, OllamaError
from doclens.retrieval import SearchIndex

STATIC = Path(__file__).parent / "static"


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=600)
    mode: Literal["rag", "search"] = "rag"


def create_app(settings: Settings | None = None, assistant: Assistant | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    index = assistant.index if assistant else SearchIndex.load(settings.corpus)
    assistant = assistant or Assistant(index, settings, OllamaClient(settings))
    app = FastAPI(title="document-search-rag", version="0.1.0")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", response_class=FileResponse)
    def home() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/info")
    def info() -> dict[str, str | int | bool]:
        return {
            "model": settings.model,
            "pages": len({c.page for c in index.chunks}),
            "chunks": len(index.chunks),
            "language": "English",
            "generation_available": not settings.search_only,
        }

    @app.get("/api/health")
    def health() -> dict[str, str | bool]:
        if settings.search_only:
            return {"corpus": True, "ollama": False, "model": settings.model}
        try:
            response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3, trust_env=False)
            response.raise_for_status()
            names = {model["name"] for model in response.json().get("models", [])}
            available = settings.model in names
        except (httpx.HTTPError, ValueError, KeyError):
            available = False
        return {"corpus": True, "ollama": available, "model": settings.model}

    @app.post("/api/ask")
    def ask(request: Question) -> dict[str, object]:
        question = request.question.strip()
        if len(question) < 3:
            raise HTTPException(422, "Enter a question with at least 3 characters.")
        if request.mode == "search":
            import time

            start = time.perf_counter()
            hits = index.search(question, settings.top_k)
            return Answer(
                "search",
                "",
                [],
                [hit.to_dict() for hit in hits],
                round((time.perf_counter() - start) * 1000, 2),
            ).to_dict()
        if settings.search_only:
            raise HTTPException(503, "This hosted demo provides excerpt search only. "
                                "Run the project locally for model answers.")
        try:
            return assistant.answer(question).to_dict()
        except OllamaError as exc:
            raise HTTPException(503, str(exc)) from exc

    return app


app = create_app()
