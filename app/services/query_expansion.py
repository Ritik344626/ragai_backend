"""Query expansion and reformulation for improved RAG retrieval."""

import re
from typing import Optional


# General conversation patterns that don't require indexed data
GENERAL_PATTERNS = {
    r"^\s*(hello|hi|hey|greetings|good morning|good afternoon|good evening)\s*$": True,
    r"^\s*(how\s+are\s+you|how\s+do\s+you\s+do|what.s\s+up)\s*$": True,
    r"^\s*(what\s+can\s+you\s+do|what\s+can\s+you\s+help|what\s+do\s+you\s+do)\s*$": True,
    r"^\s*(who\s+are\s+you|what\s+are\s+you)\s*$": True,
    r"^\s*(thanks|thank\s+you|appreciate)\s*$": True,
    r"^\s*(bye|goodbye|see\s+you)\s*$": True,
}

GENERAL_RESPONSES = {
    "hello": "Hi! I'm a RAG Assistant. I can help answer questions about trends and news from my indexed data. What would you like to know?",
    "how_are_you": "I'm functioning well, thank you for asking! How can I help you today?",
    "what_can_you_do": "I can search through indexed trends and news data to answer your questions. Ask me about AI trends, startup discussions, technology news, or any other topic you've indexed.",
    "who_are_you": "I'm a RAG (Retrieval-Augmented Generation) Assistant designed to answer questions based on indexed trends and news data using semantic search and AI summarization.",
    "thanks": "You're welcome! Feel free to ask more questions.",
    "bye": "Goodbye! Come back anytime if you have more questions.",
}

# Common synonyms for better query matching
SYNONYMS = {
    "ai": ["artificial intelligence", "machine learning", "deep learning", "neural networks"],
    "ml": ["machine learning", "ai", "algorithms"],
    "vm": ["virtual machine", "virtualization", "container"],
    "api": ["rest api", "endpoint", "interface"],
    "db": ["database", "sql", "nosql"],
    "web": ["website", "browser", "internet"],
    "app": ["application", "software", "program"],
    "bug": ["error", "issue", "problem", "defect"],
    "feature": ["capability", "functionality", "improvement"],
    "performance": ["speed", "efficiency", "optimization"],
    "security": ["authentication", "encryption", "protection"],
    "trend": ["trend", "news", "updates", "developments"],
}

INTENT_KEYWORDS = {
    "definition": ["what is", "define", "explain", "tell me about"],
    "how_to": ["how do", "how to", "how can", "steps to", "guide"],
    "comparison": ["difference between", "compare", "vs", "versus"],
    "recent": ["latest", "newest", "recent", "today", "this week"],
    "trending": ["trending", "popular", "viral", "top"],
}



def is_general_question(query: str) -> tuple[bool, Optional[str]]:
    """
    Check if query is a general conversational question (not requiring indexed data).
    
    Args:
        query: User query text
    
    Returns:
        (is_general, response_key) tuple
    """
    query_lower = query.lower().strip()
    
    for pattern, is_general in GENERAL_PATTERNS.items():
        if re.match(pattern, query_lower) and is_general:
            if "hello" in pattern or "hi" in pattern or "hey" in pattern:
                return True, "hello"
            elif "how" in pattern and "are" in pattern:
                return True, "how_are_you"
            elif "what" in pattern and ("can" in pattern or "do" in pattern):
                return True, "what_can_you_do"
            elif "who" in pattern or "what are you" in pattern:
                return True, "who_are_you"
            elif "thanks" in pattern or "thank" in pattern:
                return True, "thanks"
            elif "bye" in pattern or "goodbye" in pattern:
                return True, "bye"
    
    return False, None


def get_general_response(response_key: str) -> str:
    """Get canned response for general questions."""
    return GENERAL_RESPONSES.get(response_key, "I'm here to help! Ask me about indexed trends and news.")


def detect_intent(query: str) -> str:
    """
    Detect the intent of a query to better understand what user is asking.
    
    Args:
        query: User query
    
    Returns:
        Intent type: 'definition', 'how_to', 'comparison', 'recent', 'trending', or 'general'
    """
    query_lower = query.lower()
    
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            return intent
    
    return "general"


def expand_synonyms(query: str) -> list[str]:
    """
    Generate synonym-based expansions of query.
    
    For terms like "ai", generates "artificial intelligence", "machine learning", etc.
    
    Args:
        query: Original query
    
    Returns:
        List of synonym-expanded queries
    """
    variations = []
    query_lower = query.lower()
    
    for term, synonyms in SYNONYMS.items():
        if term in query_lower:
            for synonym in synonyms:
                expanded = query_lower.replace(term, synonym)
                if expanded not in variations and expanded != query_lower:
                    variations.append(expanded)
    
    return variations


def extract_key_entities(query: str) -> list[str]:
    """
    Extract key entities/nouns from query for focused search.
    
    Extracts meaningful terms that likely refer to indexed concepts.
    
    Args:
        query: User query
    
    Returns:
        List of key entity search queries
    """
    # Remove common question patterns
    query_cleaned = re.sub(
        r"^\s*(what|when|where|who|why|how|is|are|do|does|can|could|would|should|tell|show|explain|describe)\s+",
        "",
        query.lower()
    )
    
    # Extract words that are likely entities (3+ chars or known important short terms)
    words = query_cleaned.split()
    entities = [w for w in words if len(w) >= 3 or w in ['ai', 'ml', 'vm', 'db', 'api']]
    
    variations = []
    
    # Single entity queries
    for entity in entities:
        if entity:
            variations.append(entity)
    
    # Multi-entity combinations (first 2-3 important terms)
    if len(entities) >= 2:
        variations.append(" ".join(entities[:2]))
    if len(entities) >= 3:
        variations.append(" ".join(entities[:3]))
    
    return variations


def should_include_relaxed_search(query: str) -> bool:
    """
    Determine if query should include relaxed/fuzzy matching.
    
    Queries with typos, abbreviations, or casual language benefit from relaxed search.
    
    Args:
        query: User query
    
    Returns:
        True if relaxed search should be enabled
    """
    # Single/few word queries often need fuzzy matching
    if len(query.split()) <= 2:
        return True
    
    # Queries with abbreviations (likely to have variations)
    if any(term in query.lower() for term in ['ai', 'ml', 'vm', 'db', 'api', 'db', 'ui', 'ux']):
        return True
    
    # Casual language indicators
    if any(word in query.lower() for word in ['kinda', 'sorta', 'like', 'thing', 'stuff']):
        return True
    
    return False



def expand_query(query: str) -> list[str]:
    """
    Generate query variations to improve retrieval.
    
    Tries to rephrase the question in multiple ways to catch
    different semantic and lexical matches. Includes:
    - Question word removal
    - Statement forms
    - Synonym expansion
    - Entity extraction
    - Contextual reformulation
    
    Args:
        query: Original query
    
    Returns:
        List of query variations (including original)
    """
    variations = [query]  # Always include original
    
    query_lower = query.lower().strip()
    
    # Remove question words to create keyword-focused version
    removed_qwords = re.sub(
        r"^\s*(what|when|where|who|why|how|is|are|do|does|can|could|would|should|which|whose)\s+",
        "",
        query_lower
    )
    if removed_qwords and removed_qwords != query_lower:
        variations.append(removed_qwords)
    
    # Convert question to statement: "what is X?" -> "X"
    statement_form = re.sub(r"[?!.,:;]+$", "", query_lower).strip()
    if statement_form and statement_form != query_lower:
        variations.append(statement_form)
    
    # Extract noun phrases (simple heuristic: 2-4 consecutive non-stopword tokens)
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "of", "is", "are"
    }
    tokens = [t for t in query_lower.split() if t not in stopwords and len(t) > 2]
    if len(tokens) >= 2:
        noun_phrase = " ".join(tokens[:4])  # First 4 content tokens
        if noun_phrase and noun_phrase != query_lower:
            variations.append(noun_phrase)
    
    # Synonymous phrasings
    if "what is" in query_lower:
        definition_form = query_lower.replace("what is", "").replace("what are", "").strip()
        if definition_form:
            variations.append(f"about {definition_form}")
            variations.append(f"{definition_form} definition")
    
    if "how" in query_lower and "do" in query_lower:
        # "how do you X" -> "X process" or "X steps"
        howdo_removed = re.sub(r"how\s+(do|does|did)\s+", "", query_lower)
        if howdo_removed and howdo_removed != query_lower:
            variations.append(howdo_removed)
    
    # NEW: Add synonym expansions for known abbreviations/terms
    synonym_variations = expand_synonyms(query)
    variations.extend(synonym_variations)
    
    # NEW: Add entity-focused queries for better keyword matching
    entity_variations = extract_key_entities(query)
    variations.extend(entity_variations)
    
    # NEW: Add intent-aware reformulations
    intent = detect_intent(query)
    if intent == "definition":
        # For "what is X" -> add "X explained", "X overview"
        core = re.sub(r"what\s+(is|are|does)\s+", "", query_lower)
        if core:
            variations.extend([f"{core} explained", f"{core} overview"])
    elif intent == "how_to":
        # For "how to X" -> add "X process", "X guide", "X tutorial"
        core = re.sub(r"how\s+(to|do|does|can)\s+", "", query_lower)
        if core:
            variations.extend([f"{core} process", f"{core} guide"])
    elif intent == "comparison":
        # For "compare X and Y" -> add "X vs Y", "difference X Y"
        variations.append(query_lower.replace(" vs ", " and "))
    elif intent == "recent":
        # For "latest X" -> add "recent X", "X news", "X updates"
        core = re.sub(r"(latest|newest|recent)\s+", "", query_lower)
        if core:
            variations.extend([f"recent {core}", f"{core} news", f"{core} updates"])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        v_normalized = v.strip().lower()
        if v_normalized and v_normalized not in seen and len(v_normalized) >= 2:
            seen.add(v_normalized)
            unique_variations.append(v)
    
    # Limit to reasonable number of variants to avoid too many searches
    return unique_variations[:8]


def should_relax_thresholds(query: str) -> bool:
    """
    Determine if query deserves relaxed/lenient retrieval thresholds.
    
    Short queries or those with low semantic specificity may need lower bars.
    
    Args:
        query: User query
    
    Returns:
        True if thresholds should be relaxed
    """
    # Very short queries often need help finding matches
    if len(query.split()) <= 3:
        return True
    
    # Queries with numbers/dates might be specific enough already
    if re.search(r"\d{4}|\d{1,2}/\d{1,2}", query):
        return False
    
    # Open-ended questions ("what", "tell me") may need relaxation
    if any(q in query.lower() for q in ["what", "tell me", "explain", "describe"]):
        return True
    
    # Abbreviations and short terms need relaxation
    if should_include_relaxed_search(query):
        return True
    
    return False


def suggest_related_topics(query: str) -> list[str]:
    """
    Suggest related search topics when initial query finds nothing.
    
    Generates related concepts that might have indexed data.
    
    Args:
        query: Original query
    
    Returns:
        List of related topic suggestions
    """
    suggestions = []
    query_lower = query.lower()
    
    # If looking for something specific, suggest broader versions
    if "latest" in query_lower or "newest" in query_lower:
        broader = query_lower.replace("latest ", "").replace("newest ", "")
        suggestions.append(broader)
    
    # If looking for a definition, suggest just the term
    if "what is" in query_lower or "define" in query_lower:
        term = query_lower.replace("what is", "").replace("define", "").strip()
        suggestions.append(term)
    
    # Suggest parent concepts
    if "machine learning" in query_lower:
        suggestions.extend(["ai", "artificial intelligence", "deep learning"])
    if "deep learning" in query_lower:
        suggestions.extend(["machine learning", "neural networks", "ai"])
    if "api" in query_lower:
        suggestions.extend(["rest", "integration", "web service"])
    if "database" in query_lower or "db" in query_lower:
        suggestions.extend(["sql", "nosql", "data"])
    
    # Remove duplicates and original
    suggestions = list(set(suggestions))
    suggestions = [s for s in suggestions if s.lower() != query_lower]
    
    return suggestions[:3]  # Return top 3 suggestions
