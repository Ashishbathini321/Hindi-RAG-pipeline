"""Command-line entry point for the Hindi PDF RAG assignment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.answering import GeneratedAnswer, citation, generate_answer
from app.pdf_text import extract_pdf_pages
from app.text_processing import build_chunks, normalize_text
from app.vector_store import DEFAULT_EMBEDDING_MODEL, Embedder, ingest_chunks, retrieve


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "chroma_db"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "test_answers.md"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def add_shared_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Folder for local Chroma data.")
    parser.add_argument("--collection", default="agni_ki_udaan_hindi", help="Chroma collection name.")
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="Sentence-Transformers multilingual embedding model.",
    )


def add_answer_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--top-k", type=positive_int, default=4, help="How many chunks to retrieve.")
    parser.add_argument(
        "--generator",
        choices=["extractive", "ollama"],
        default="extractive",
        help="extractive needs no service; ollama produces a concise local-LLM answer.",
    )
    parser.add_argument("--ollama-model", default="qwen2.5:3b", help="Local Ollama model when using --generator ollama.")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG over the supplied Hindi Kalam PDF.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subcommands.add_parser("ingest", help="Extract, normalize, chunk, and index a PDF.")
    ingest_parser.add_argument("--pdf", type=Path, required=True, help="Path to Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf")
    ingest_parser.add_argument("--chunk-words", type=positive_int, default=180, help="Maximum words per chunk.")
    ingest_parser.add_argument("--overlap-words", type=int, default=30, help="Complete-sentence overlap between chunks.")
    ingest_parser.add_argument("--preview", action="store_true", help="Print chunk metadata and a short text preview.")
    add_shared_options(ingest_parser)

    ask_parser = subcommands.add_parser("ask", help="Ask one Hindi or English question.")
    ask_parser.add_argument("--query", required=True, help="Question in Hindi or English.")
    add_shared_options(ask_parser)
    add_answer_options(ask_parser)

    tests_parser = subcommands.add_parser("run-tests", help="Run the six required test queries and save cited answers.")
    tests_parser.add_argument("--queries", type=Path, default=PROJECT_ROOT / "test_queries.json")
    tests_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    add_shared_options(tests_parser)
    add_answer_options(tests_parser)
    return parser


def answer_one(
    args: argparse.Namespace, query: str, embedder: Embedder
) -> tuple[GeneratedAnswer, list[dict[str, object]]]:
    normalized_query = normalize_text(query)
    results = retrieve(normalized_query, args.db_path, args.collection, embedder, args.top_k)
    answer = generate_answer(normalized_query, results, args.generator, args.ollama_model, embedder)
    return answer, results


def run_ingest(args: argparse.Namespace) -> None:
    if not args.pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")
    pages = extract_pdf_pages(args.pdf)
    chunks = build_chunks(pages, max_words=args.chunk_words, overlap_words=args.overlap_words)
    embedder = Embedder(args.embedding_model)
    count = ingest_chunks(chunks, args.db_path, args.collection, embedder)
    print(f"Indexed {count} chunks from {len(pages)} pages in {args.db_path}.")
    if args.preview:
        for chunk in chunks[:8]:
            print(f"{chunk.chunk_id} | page {chunk.page} | {chunk.section}\n{chunk.text[:220]}\n")


def print_answer(query: str, answer: GeneratedAnswer, results: list[dict[str, object]]) -> None:
    print(f"Query: {query}\n")
    print(f"Answer: {answer.text}\n")
    print("Primary source (automatic citation):")
    for result in answer.primary_sources:
        print(f"- {citation(result)}")
    additional = [result for result in results if result not in answer.primary_sources]
    if additional:
        print("Additional retrieved context:")
        for result in additional:
            print(f"- {citation(result)}")


def run_ask(args: argparse.Namespace) -> None:
    embedder = Embedder(args.embedding_model)
    answer, results = answer_one(args, args.query, embedder)
    print_answer(args.query, answer, results)


def run_tests(args: argparse.Namespace) -> None:
    payload = json.loads(args.queries.read_text(encoding="utf-8"))
    queries = payload["queries"]
    if len(queries) != 6:
        raise ValueError("The required test file must contain exactly six queries.")

    embedder = Embedder(args.embedding_model)
    lines = ["# Required test-query results", "", "Generated by `python main.py run-tests`.", ""]
    for item in queries:
        query = item["query"]
        answer, results = answer_one(args, query, embedder)
        lines.extend([
            f"## {item['id']}. {item['language']}",
            "",
            f"**Query:** {query}",
            "",
            f"**Answer:** {answer.text}",
            "",
            "**Primary source (automatic citation):**",
        ])
        lines.extend([f"- {citation(result)}" for result in answer.primary_sources])
        additional = [result for result in results if result not in answer.primary_sources]
        if additional:
            lines.extend(["", "**Additional retrieved context:**"])
            lines.extend([f"- {citation(result)}" for result in additional])
        lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 BOM keeps Windows PowerShell 5.1's default Get-Content display
    # correct for Hindi, while modern tools still read it as ordinary UTF-8.
    args.output.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"Wrote six cited answers to {args.output}")


def main() -> None:
    # Windows Command Prompt may default to cp1252, which cannot print Hindi.
    # Reconfigure only when the stream supports it (for normal terminal use).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = make_parser()
    args = parser.parse_args()
    if args.command == "ingest":
        run_ingest(args)
    elif args.command == "ask":
        run_ask(args)
    elif args.command == "run-tests":
        run_tests(args)


if __name__ == "__main__":
    main()
