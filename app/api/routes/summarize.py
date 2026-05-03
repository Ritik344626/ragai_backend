from difflib import SequenceMatcher
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.connection import get_db
from app.services.query_expansion import (
    expand_query,
    get_general_response,
    is_general_question,
    should_relax_thresholds,
)
from app.services.rag import search_chunks
from app.services.summarization import generate_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summarize", tags=["summarization"])

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")  # Allow 2+ chars to capture short terms like "vm", "ai", "ml"
_STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "from",
    "this",
    "what",
    "when",
    "where",
    "which",
    "about",
    "your",
    "into",
    "have",
    "will",
    "are",
    "was",
    "were",
}


def _tokenize(text: str) -> set[str]:
    tokens = {match.group(0).lower() for match in _TOKEN_RE.finditer(text)}
    return {token for token in tokens if token not in _STOPWORDS}


def _tokens_match(query_token: str, chunk_token: str) -> bool:
    if query_token == chunk_token:
        return True
    if not settings.rag_enable_fuzzy_lexical_match:
        return False
    if len(query_token) < 5 or len(chunk_token) < 5:
        return False
    ratio = SequenceMatcher(None, query_token, chunk_token).ratio()
    return ratio >= settings.rag_fuzzy_token_match_ratio


def _lexical_overlap_ratio(query: str, chunk_text: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0

    matched = 0
    for query_token in query_tokens:
        if any(_tokens_match(query_token, chunk_token) for chunk_token in chunk_tokens):
            matched += 1

    return matched / len(query_tokens)


def _evaluate_candidates(topic: str, chunks: list[dict]) -> dict:
    strict_candidates: list[dict] = []
    relaxed_candidates: list[dict] = []

    for chunk in chunks:
        similarity = float(chunk.get("similarity_score", 0.0))
        lexical_overlap = _lexical_overlap_ratio(topic, str(chunk.get("text", "")))
        hybrid_score = (0.75 * similarity) + (0.25 * lexical_overlap)
        semantic_override = similarity >= settings.rag_strong_similarity_override
        strict_pass = (
            semantic_override
            or (
                similarity >= settings.rag_min_similarity_for_context
                and lexical_overlap >= settings.rag_min_lexical_overlap_for_context
                and hybrid_score >= settings.rag_min_hybrid_score_for_context
            )
        )
        relaxed_pass = (
            similarity >= settings.rag_relaxed_min_similarity_for_context
            and lexical_overlap >= settings.rag_relaxed_min_lexical_overlap_for_context
            and hybrid_score >= settings.rag_relaxed_min_hybrid_score_for_context
        ) or semantic_override

        chunk["lexical_overlap"] = lexical_overlap
        chunk["hybrid_score"] = hybrid_score
        chunk["semantic_override"] = semantic_override

        if strict_pass:
            strict_candidates.append(chunk)
        if relaxed_pass:
            relaxed_candidates.append(chunk)

    relevant_chunks = strict_candidates
    relevance_mode = "strict"
    if (
        len(relevant_chunks) < settings.rag_min_relevant_chunks
        and settings.rag_enable_relaxed_fallback
    ):
        relevant_chunks = relaxed_candidates
        relevance_mode = "relaxed"

    relevant_chunks.sort(
        key=lambda chunk: float(chunk.get("hybrid_score", 0.0)),
        reverse=True,
    )

    selected_chunks: list[dict] = []
    per_source_count: dict[str, int] = {}
    for chunk in relevant_chunks:
        source_id = str(chunk.get("source_id", "unknown"))
        current = per_source_count.get(source_id, 0)
        if current >= settings.rag_max_chunks_per_source:
            continue
        selected_chunks.append(chunk)
        per_source_count[source_id] = current + 1
        if len(selected_chunks) >= settings.rag_max_sources_for_summary:
            break

    if len(selected_chunks) < settings.rag_min_relevant_chunks:
        selected_chunks = []
        relevance_mode = "none"

    return {
        "strict_candidates": strict_candidates,
        "relaxed_candidates": relaxed_candidates,
        "selected_chunks": selected_chunks,
        "relevance_mode": relevance_mode,
    }


@router.get("/topic")
def summarize_topic(
    topic: str = Query(..., min_length=1, description="Topic or query to summarize"),
    limit: int = Query(default=5, ge=1, le=20, description="Number of chunks to retrieve"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Search for relevant information on a topic and generate an AI summary using Gemini.
    
    Handles:
    - General conversational questions (hello, how are you, etc)
    - Query variations and paraphrasing
    - Progressive threshold relaxation if no results found
    
    Args:
        topic: The topic or question to search and summarize
        limit: Number of relevant chunks to retrieve
        db: Database session
    
    Returns:
        dict with:
        - query: Original topic
        - summary: AI-generated summary or conversational response
        - sources: List of sources used (if grounded)
        - chunk_count: Number of chunks retrieved
    """
    try:
        # Check if this is a general conversational question
        is_general, response_key = is_general_question(topic)
        if is_general and response_key:
            logger.info(
                "Conversational query detected",
                extra={"query": topic, "response_type": response_key}
            )
            return {
                "query": topic,
                "summary": get_general_response(response_key),
                "sources": [],
                "chunk_count": 0,
                "is_grounded": False,
                "is_conversational": True,
            }
        
        # Expand query into multiple variations
        query_variations = expand_query(topic)
        candidate_limit = min(max(limit * 6, 20), 80)
        
        logger.debug(
            "Query expansion performed",
            extra={
                "original_query": topic,
                "num_variants": len(query_variations),
                "variants": query_variations,
            }
        )
        
        # Try retrieving with multiple query variations
        all_chunks: dict = {}  # chunk_id -> chunk (to deduplicate)
        for variant_query in query_variations:
            chunks = search_chunks(db, variant_query, limit=candidate_limit)
            logger.debug(
                "Variant search result",
                extra={"variant": variant_query, "chunks_found": len(chunks)}
            )
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id")
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
        
        chunks_list = list(all_chunks.values())
        evaluation = _evaluate_candidates(topic, chunks_list)
        relevant_chunks = evaluation["selected_chunks"]
        
        logger.info(
            "Chunk evaluation completed",
            extra={
                "query": topic,
                "total_candidates": len(chunks_list),
                "strict_candidates": len(evaluation["strict_candidates"]),
                "relaxed_candidates": len(evaluation["relaxed_candidates"]),
                "selected_chunks": len(relevant_chunks),
                "relevance_mode": evaluation["relevance_mode"],
            }
        )
        
        # If no results and query is short/open-ended, relax thresholds
        if (
            not relevant_chunks
            and should_relax_thresholds(topic)
            and evaluation["relaxed_candidates"]
        ):
            # Use relaxed candidates as fallback
            logger.info(
                "Threshold relaxation applied",
                extra={
                    "query": topic,
                    "reason": "short/open-ended query with no strict matches",
                    "fallback_chunks": len(evaluation["relaxed_candidates"][:limit])
                }
            )
            relevant_chunks = evaluation["relaxed_candidates"][:limit]
        
        # Generate summary using Gemini
        result = generate_summary(topic, relevant_chunks)
        result["query_expanded"] = len(query_variations) > 1
        result["num_variants_tried"] = len(query_variations)
        
        logger.info(
            "Summary generated successfully",
            extra={
                "query": topic,
                "is_grounded": result.get("is_grounded"),
                "chunk_count": result.get("chunk_count"),
                "query_expanded": result.get("query_expanded"),
            }
        )
        
        return result
        
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Summarization failed: {str(exc)}",
        ) from exc
