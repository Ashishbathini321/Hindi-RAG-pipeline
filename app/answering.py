"""Grounded answer generation and automatic source-citation formatting."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from .text_processing import split_sentences
from .vector_store import Embedder


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    primary_sources: list[dict[str, object]]


def citation(result: dict[str, object]) -> str:
    metadata = result["metadata"]
    assert isinstance(metadata, dict)
    return (
        f'page: {metadata["page"]} · section: "{metadata["section"]}" '
        f'· chunk_id: {metadata["chunk_id"]} · score: {float(result["score"]):.3f}'
    )


def _context(results: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for result in results:
        blocks.append(f"[{citation(result)}]\n{result['text']}")
    return "\n\n".join(blocks)


def _answer_shape_bonus(query: str, sentence: str) -> float:
    """Small language-agnostic cues that break ties among nearby source sentences."""
    query_lower = query.lower()
    bonus = 0.0
    if any(word in query_lower for word in ("institution", "college", "university", "संस्थान")):
        if re.search(r"प्रवेश|admission|enrolled|एमआईटी", sentence, re.I):
            bonus += 0.35
        elif re.search(r"इं.?ट.?ट.?यू.?ट|कॉलेज|institute|university", sentence, re.I):
            bonus += 0.08
    if any(word in query_lower for word in ("year", "when", "published", "वर्ष")) and re.search(r"\d{4}", sentence):
        bonus += 0.06
    return bonus


def _lexical_grounding_bonus(query: str, sentence: str) -> float:
    """Reward explicit question terms so a supported fact beats generic biography text."""
    stop_words = {
        "a", "an", "and", "are", "did", "for", "how", "in", "is", "of", "the", "to", "what", "when", "which", "who",
        "का", "की", "के", "को", "किस", "क्या", "ने", "में", "और", "है", "था", "थी", "हुआ", "वह",
    }
    tokens = lambda text: set(re.findall(r"[\w-]+", text.lower(), flags=re.UNICODE))
    query_terms = {term for term in tokens(query) if len(term) > 1 and term not in stop_words}
    matches = query_terms & tokens(sentence)
    bonus = min(0.45, 0.15 * len(matches))

    # Preserve the original Unicode words for exact multi-word facts such as
    # "भारत रत्न". The token regex above intentionally simplifies combining
    # marks, so it is not suitable for phrase matching by itself.
    raw_words = [word.strip("?!.:;,").lower() for word in query.split()]
    for first, second in zip(raw_words, raw_words[1:]):
        if first and second and first not in stop_words and second not in stop_words:
            if f"{first} {second}" in sentence.lower():
                bonus += 0.35
                break

    if "भूमिका" in query and re.search(r"संगठनात्मक|भूमिका|भूमका", sentence):
        bonus += 0.30
    return min(0.80, bonus)


def extractive_answer(
    query: str, results: list[dict[str, object]], embedder: Embedder
) -> GeneratedAnswer:
    """Quote the most semantically relevant retrieved sentence without inventing facts."""
    if not results:
        return GeneratedAnswer(
            "The supplied document does not contain enough retrieved context to answer this.", []
        )

    candidates: list[tuple[str, float, dict[str, object]]] = []
    for result in results:
        chunk_score = float(result["score"])
        for sentence in split_sentences(str(result["text"])):
            # The study guide contains review questions. They can have excellent
            # semantic similarity but are not valid answers, so exclude them.
            if len(sentence.split()) >= 4 and not sentence.rstrip().endswith("?"):
                candidates.append((sentence, chunk_score, result))
    if not candidates:
        return GeneratedAnswer(str(results[0]["text"]), [results[0]])

    semantic_scores = embedder.score_passages_against_query(
        query, [sentence for sentence, _, _ in candidates]
    )
    # Sentence similarity identifies the answer-bearing sentence; a small chunk
    # score component stabilizes close ties without changing the source evidence.
    best_index = max(
        range(len(candidates)),
        key=lambda index: (
            0.85 * semantic_scores[index]
            + 0.15 * candidates[index][1]
            + _answer_shape_bonus(query, candidates[index][0])
            + _lexical_grounding_bonus(query, candidates[index][0])
        ),
    )
    sentence, _, source = candidates[best_index]
    return GeneratedAnswer(sentence, [source])


def ollama_answer(
    query: str, results: list[dict[str, object]], model: str, embedder: Embedder
) -> GeneratedAnswer:
    """Use a local Ollama model. Citations are attached by this application afterwards."""
    evidence = extractive_answer(query, results, embedder)
    prompt = f"""You are answering questions about one supplied Hindi study-guide PDF.
Use only the primary evidence sentence below. Do not use outside knowledge or
other biography facts. Answer every part of the question directly and concisely
in the language of the question; for example, include both a person's name and
a year when both are requested. Do not restate the question. For English
answers, translate ordinary prose but preserve acronyms exactly (for example,
एमआईटी is MIT) and never substitute a different institution. Do not invent
citations or page numbers; the application will attach them.

Question: {query}

Primary evidence:
{evidence.text}
"""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode(
        "utf-8"
    )
    request = Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama at http://localhost:11434. Start Ollama, run "
            f"`ollama pull {model}`, or choose --generator extractive."
        ) from exc
    answer = str(body.get("response", "")).strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty answer.")
    return GeneratedAnswer(answer, evidence.primary_sources)


def generate_answer(
    query: str,
    results: list[dict[str, object]],
    generator: str,
    ollama_model: str,
    embedder: Embedder,
) -> GeneratedAnswer:
    if generator == "extractive":
        return extractive_answer(query, results, embedder)
    if generator == "ollama":
        return ollama_answer(query, results, ollama_model, embedder)
    raise ValueError(f"Unsupported generator: {generator}")
