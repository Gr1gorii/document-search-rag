"""Compare search and local RAG; write every actual result before summarizing it."""

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from typing import Any

from doclens.config import ROOT, Settings
from doclens.rag import Assistant, ModelAnswer, OllamaClient, OllamaError
from doclens.retrieval import Hit, SearchIndex, query_coverage


class RecordingClient(OllamaClient):
    """The evaluator runs sequentially; keep one draft for the inspectable trace."""

    draft: ModelAnswer | None = None

    def generate(self, question: str, hits: list[Hit]) -> ModelAnswer:
        self.draft = super().generate(question, hits)
        return self.draft


def keyword_pass(text: str, groups: list[list[str]]) -> bool:
    return all(any(term.casefold() in text.casefold() for term in group) for group in groups)


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def latency(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50_ms": None, "p95_ms": None}
    ordered = sorted(values)
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 2),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if row["answerable"]]
    negatives = [row for row in rows if not row["answerable"]]
    rag_rows = [row for row in rows if "rag" in row]
    rag_pos = [row for row in positives if "rag" in row]
    rag_neg = [row for row in negatives if "rag" in row]
    answered = [row for row in rag_rows if row["rag"]["status"] == "answered"]
    citations = [citation for row in answered for citation in row["rag"]["citations"]]
    relevant = sum(
        citation["page"] in row["gold_pages"]
        for row in answered
        for citation in row["rag"]["citations"]
    )
    return {
        "questions": len(rows),
        "answerable": len(positives),
        "unanswerable": len(negatives),
        "reviewed_questions": sum(row["review_status"] != "draft_unreviewed" for row in rows),
        "search": {
            "gold_page_hit_at_1": mean([float(row["rank"] == 1) for row in positives]),
            "gold_page_hit_at_4": mean([float(row["rank"] > 0) for row in positives]),
            "mrr_at_4": mean([1 / row["rank"] if row["rank"] else 0.0 for row in positives]),
            "evidence_keyword_pass_at_4": mean(
                [float(row["retrieved_keyword_pass"]) for row in positives]
            ),
            "gate_abstention_on_unanswerable": mean(
                [float(row["gate_abstained"]) for row in negatives]
            ),
            "latency": latency([row["search_latency_ms"] for row in rows]),
        },
        "rag": {
            "completed": len(rag_rows),
            "errors": sum(row["rag"]["status"] == "error" for row in rag_rows),
            "answered": len(answered),
            "answer_keyword_pass_on_answerable": mean(
                [
                    float(row["rag"]["status"] == "answered" and row["answer_keyword_pass"])
                    for row in rag_pos
                ]
            ),
            "answer_and_gold_citation_proxy": mean(
                [
                    float(
                        row["rag"]["status"] == "answered"
                        and row["answer_keyword_pass"]
                        and any(c["page"] in row["gold_pages"] for c in row["rag"]["citations"])
                    )
                    for row in rag_pos
                ]
            ),
            "abstention_recall": mean(
                [float(row["rag"]["status"] == "abstained") for row in rag_neg]
            ),
            "false_abstention_on_answerable": mean(
                [float(row["rag"]["status"] == "abstained") for row in rag_pos]
            ),
            "citation_page_precision": round(relevant / len(citations), 4) if citations else None,
            "citation_id_validity": mean([float(row["citation_ids_valid"]) for row in answered]),
            "latency_all": latency([row["rag"]["latency_ms"] for row in rag_rows]),
            "latency_answered": latency([row["rag"]["latency_ms"] for row in answered]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Call the already installed local model"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dataset", default="eval/questions.json")
    parser.add_argument("--output", default="reports/evaluation")
    args = parser.parse_args()
    settings = Settings.from_env()
    index = SearchIndex.load(settings.corpus)
    client = RecordingClient(settings)
    assistant = Assistant(index, settings, client)
    dataset_path = ROOT / args.dataset
    questions = json.loads(dataset_path.read_text())
    if args.limit:
        questions = questions[: args.limit]
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with output.with_suffix(".jsonl").open("w", encoding="utf-8") as log:
        for item in questions:
            start = time.perf_counter()
            hits = index.search(item["question"], settings.top_k)
            elapsed = (time.perf_counter() - start) * 1000
            ranks = [i for i, hit in enumerate(hits, 1) if hit.chunk.page in item["gold_pages"]]
            row = {
                **item,
                "retrieved": [hit.to_dict() for hit in hits],
                "rank": min(ranks) if ranks else 0,
                "search_latency_ms": elapsed,
                "query_coverage": query_coverage(item["question"], hits),
                "gate_abstained": (
                    not hits
                    or hits[0].score < settings.min_score
                    or query_coverage(item["question"], hits) < settings.min_coverage
                ),
                "retrieved_keyword_pass": keyword_pass(
                    "\n".join(hit.chunk.text for hit in hits), item["expected_terms"]
                ),
            }
            if args.live:
                client.draft = None
                start = time.perf_counter()
                try:
                    answer = assistant.answer(item["question"])
                    row["rag"] = answer.to_dict()
                except OllamaError as exc:
                    row["rag"] = {
                        "status": "error",
                        "answer": str(exc),
                        "citations": [],
                        "latency_ms": (time.perf_counter() - start) * 1000,
                    }
                row["answer_keyword_pass"] = keyword_pass(
                    row["rag"]["answer"], item["expected_terms"]
                )
                known = {hit.chunk.id for hit in hits}
                row["citation_ids_valid"] = all(
                    citation["id"] in known for citation in row["rag"]["citations"]
                )
                row["model_output"] = client.draft.model_dump() if client.draft else None
            rows.append(row)
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            print(
                f"{item['id']}: retrieval rank={row['rank']} "
                f"rag={row.get('rag', {}).get('status', 'not run')}",
                flush=True,
            )
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.model,
        "dataset": args.dataset,
        "platform": platform.platform(),
        "min_score": settings.min_score,
        "min_coverage": settings.min_coverage,
        "top_k": settings.top_k,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(settings.corpus.read_bytes()).hexdigest(),
        "metrics": summarize(rows),
        "limitations": [
            "Draft labels; this run is not an independent manual review of the answers.",
            "Keyword matching is an answer-content proxy, not semantic correctness.",
            "Gold-page relevance and citation ID validity do not prove sentence-level support.",
            "The dataset was authored for this corpus; "
            "no independently reviewed external benchmark.",
            "The coverage guard was added after observing failures on this development set.",
            "Latency is from one sequential local run; model loading and hardware affect results.",
        ],
    }
    output.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["metrics"], indent=2))


if __name__ == "__main__":
    main()
