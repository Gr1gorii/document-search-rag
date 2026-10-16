import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    corpus: Path = ROOT / "data" / "chunks.json"
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:1.7b"
    timeout: float = 90.0
    min_score: float = 2.0
    min_coverage: float = 0.6
    top_k: int = 4
    search_only: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.getenv("DOCLENS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("DOCLENS_OLLAMA_URL must point to a local HTTP Ollama server")
        return cls(
            corpus=Path(os.getenv("DOCLENS_CORPUS", str(ROOT / "data" / "chunks.json"))),
            ollama_url=url,
            model=os.getenv("DOCLENS_MODEL", "qwen3:1.7b"),
            search_only=os.getenv("DOCLENS_SEARCH_ONLY", "false").lower() == "true",
        )
