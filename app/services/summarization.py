import json
import re

import google.generativeai as genai

from app.core.config import settings

# Configure Gemini API
genai.configure(api_key=settings.gemini_api_key)

FALLBACK_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
]
_JSON_OBJECT_RE = re.compile(r"\{.*\}", flags=re.DOTALL)


def _normalize_model_name(model_name: str) -> str:
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _discover_generate_models() -> list[str]:
    """Return model names that support generateContent for the current API key."""
    discovered: list[str] = []
    try:
        for model in genai.list_models():
            methods = getattr(model, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                discovered.append(model.name)
    except Exception:
        return []

    return discovered


def _build_model_candidates() -> list[str]:
    candidates: list[str] = []

    # 1) User configured model first
    if settings.gemini_model:
        candidates.append(_normalize_model_name(settings.gemini_model))

    # 2) Known public fallback models
    for model_name in FALLBACK_MODELS:
        normalized = _normalize_model_name(model_name)
        if normalized not in candidates:
            candidates.append(normalized)

    # 3) Models discovered from current key/project capability
    for discovered in _discover_generate_models():
        if discovered not in candidates:
            candidates.append(discovered)

    return candidates


def _run_gemini(prompt: str) -> str:
    model_candidates = _build_model_candidates()

    last_error = ""
    for model_name in model_candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response.text:
                return response.text.strip()
        except Exception as exc:
            last_error = str(exc)

    if last_error:
        return f"Error generating summary: {last_error}"
    return "Error generating summary: no model response."


def _grounded_no_data_message() -> str:
    return (
        "I do not have enough relevant indexed data for a reliable answer yet. "
        "Please ingest/index more topic-specific sources and try again."
    )


def _extract_json_object(text: str) -> dict | None:
    candidate = text.strip()
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def generate_summary(query: str, retrieved_chunks: list[dict]) -> dict:
    """
    Generate a summary from retrieved chunks using Gemini.
    
    Args:
        query: Original user query
        retrieved_chunks: List of chunks from semantic search
    
    Returns:
        dict with summary, sources, and metadata
    """
    if not retrieved_chunks:
        return {
            "query": query,
            "summary": _grounded_no_data_message(),
            "sources": [],
            "chunk_count": 0,
            "is_grounded": False,
        }
    
    # Truncate chunk content to prevent token overflow (Gemini has context limits)
    MAX_CHUNK_LENGTH = 400  # tokens ≈ 4x chars, so 400 * 4 = 1600 chars roughly
    truncated_chunks = []
    for chunk in retrieved_chunks:
        truncated_chunk = chunk.copy()
        chunk_text = chunk.get("text", "")
        if len(chunk_text) > MAX_CHUNK_LENGTH:
            truncated_chunk["text"] = chunk_text[:MAX_CHUNK_LENGTH] + "..."
        truncated_chunks.append(truncated_chunk)
    
    # Prepare context from chunks
    context = "\n\n---\n\n".join(
        [
            f"Evidence ID: E{idx}\n"
            f"Source: {chunk.get('source_id', 'Unknown')}\n"
            f"URL: {chunk.get('url', 'N/A')}\n"
            f"Published: {chunk.get('published_at', 'N/A')}\n"
            f"Content:\n{chunk['text']}"
            for idx, chunk in enumerate(truncated_chunks, start=1)
        ]
    )
    
    # Strict grounded prompt with structured JSON response.
    prompt = f"""You are a strict grounded RAG assistant.
Answer ONLY from Retrieved Context below.
Do NOT add outside facts, prior knowledge, or definitions.
Do NOT include evidence IDs in the answer text.

Return ONLY this exact JSON format (valid JSON, no extra text):
{{
  "answer": "Your 1-2 sentence answer here",
  "evidence_bullets": ["Key point 1 [E1]", "Key point 2 [E2]"],
  "used_evidence_ids": ["E1", "E2"],
  "is_grounded": true
}}

If insufficient evidence, set is_grounded to false and provide a brief answer.

User Query: {query}

Retrieved Context:
{context}
"""
    raw_text = _run_gemini(prompt)
    
    # Parse JSON with better error handling
    parsed = _extract_json_object(raw_text)

    summary_text = _grounded_no_data_message()
    used_ids: list[str] = []
    is_grounded = False

    if parsed is not None:
        answer = str(parsed.get("answer", "")).strip()
        bullets_raw = parsed.get("evidence_bullets", [])
        used_raw = parsed.get("used_evidence_ids", [])
        parsed_grounded = bool(parsed.get("is_grounded", False))

        # Extract and clean bullets
        bullets: list[str] = []
        if isinstance(bullets_raw, list):
            bullets = [str(item).strip() for item in bullets_raw if str(item).strip()]
        
        # Extract and clean evidence IDs
        if isinstance(used_raw, list):
            used_ids = [str(item).strip().upper() for item in used_raw if str(item).strip()]
        
        # Validate answer is not empty or malformed
        if answer and len(answer) > 10 and not answer.startswith("- E"):
            summary_lines = [answer]
            for bullet in bullets[:3]:
                # Remove any stray evidence markers from bullets
                clean_bullet = re.sub(r'\s*-\s*E\d+\s*$', '', bullet).strip()
                if clean_bullet and clean_bullet != bullet:
                    # Bullet was malformed, reattach evidence properly
                    match = re.search(r'\[E\d+\]', bullet)
                    if match:
                        clean_bullet += f" {match.group(0)}"
                if clean_bullet:
                    summary_lines.append(f"- {clean_bullet}")
            
            summary_text = "\n".join(summary_lines)
            is_grounded = parsed_grounded
        else:
            # Answer was malformed or too short
            summary_text = _grounded_no_data_message()
            is_grounded = False
    else:
        # Safe fallback: do not propagate unstructured model output as factual answer.
        summary_text = _grounded_no_data_message()
        is_grounded = False
    
    # Prepare sources list
    id_to_chunk: dict[str, dict] = {
        f"E{idx}": chunk for idx, chunk in enumerate(retrieved_chunks, start=1)
    }

    filtered_chunks: list[dict] = []
    seen_ids: set[str] = set()
    for evidence_id in used_ids:
        if evidence_id in id_to_chunk and evidence_id not in seen_ids:
            filtered_chunks.append(id_to_chunk[evidence_id])
            seen_ids.add(evidence_id)

    if not filtered_chunks:
        filtered_chunks = retrieved_chunks[:3]  # Limit to top 3

    sources = [
        {
            "source_id": chunk.get("source_id"),
            "url": chunk.get("url"),
            "published_at": chunk.get("published_at"),
            "similarity_score": chunk.get("similarity_score", 0),
            "lexical_overlap": chunk.get("lexical_overlap", 0),
            "hybrid_score": chunk.get("hybrid_score", 0),
            "semantic_override": chunk.get("semantic_override", False),
        }
        for chunk in filtered_chunks
    ]
    
    return {
        "query": query,
        "summary": summary_text,
        "sources": sources,
        "chunk_count": len(filtered_chunks),
        "is_grounded": is_grounded,
    }
