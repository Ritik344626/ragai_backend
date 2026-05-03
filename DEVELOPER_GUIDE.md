# Developer Guide: Using Query Understanding Features

## Quick Integration

All features are automatically integrated into the `/api/v1/summarize/topic` endpoint. No code changes needed to use them!

### API Endpoint Behavior

```python
# User sends this:
GET /api/v1/summarize/topic?topic=what+is+macOS+VM

# System automatically:
# 1. Detects intent: "definition"
# 2. Generates 8 query variants
# 3. Searches all variants in parallel
# 4. Deduplicates results
# 5. Evaluates with hybrid scoring
# 6. Relaxes thresholds if needed
# 7. Returns AI summary

# Response includes:
{
  "query": "what is macOS VM",
  "summary": "macOS VM refers to virtual machine technology...",
  "is_grounded": true,
  "query_expanded": true,
  "num_variants_tried": 8,
  "chunk_count": 3,
  "sources": [...]
}
```

## Direct Function Usage

### For Custom Implementations

```python
from app.services.query_expansion import (
    expand_query,
    detect_intent,
    expand_synonyms,
    extract_key_entities,
    should_include_relaxed_search,
    suggest_related_topics,
    is_general_question,
    get_general_response,
)

# 1. Check if conversational
is_general, response_key = is_general_question("hello")
if is_general:
    response = get_general_response(response_key)
    # Returns: "Hi! I'm a RAG Assistant..."

# 2. Detect intent
intent = detect_intent("what is AI")
# Returns: "definition"

# 3. Expand query into variants
variants = expand_query("what is macOS VM")
# Returns: ['what is macOS VM', 'is macos vm', 'about macos vm', ...]

# 4. Get synonyms
synonyms = expand_synonyms("tell me about AI")
# Returns: ['tell me about artificial intelligence', 'tell me about machine learning', ...]

# 5. Extract entities
entities = extract_key_entities("latest neural network research")
# Returns: ['latest', 'neural', 'network', 'research', 'latest neural network', ...]

# 6. Check if relaxed search needed
relaxed = should_include_relaxed_search("what is ML")
# Returns: True (short + abbreviation)

# 7. Get related topics
related = suggest_related_topics("machine learning")
# Returns: ['ai', 'artificial intelligence', 'deep learning']
```

## Advanced Usage Patterns

### Pattern 1: Custom Query Rewriting

```python
from app.services.query_expansion import detect_intent, expand_synonyms

def custom_query_handler(user_query: str):
    intent = detect_intent(user_query)
    
    if intent == "definition":
        # For definition requests, emphasize explanation
        custom_query = f"explain {user_query.replace('what is ', '')}"
    elif intent == "comparison":
        # For comparisons, focus on differences
        custom_query = f"differences {user_query}"
    elif intent == "recent":
        # For recent, add temporal indicator
        custom_query = f"{user_query} 2024 2025"
    else:
        custom_query = user_query
    
    return custom_query
```

### Pattern 2: Multi-Intent Handling

```python
from app.services.query_expansion import detect_intent

def handle_query_by_intent(query: str, db: Session):
    intent = detect_intent(query)
    
    if intent == "comparison":
        # Use different search strategy for comparisons
        return comparison_search(query, db)
    elif intent == "how_to":
        # Focus on process/tutorial chunks
        return process_search(query, db)
    elif intent == "recent":
        # Sort by date published
        return recent_search(query, db)
    elif intent == "definition":
        # Look for introductory/explanatory content
        return definition_search(query, db)
    else:
        # Standard search
        return standard_search(query, db)
```

### Pattern 3: Fallback Chain

```python
from app.services.query_expansion import (
    expand_query, 
    suggest_related_topics,
    extract_key_entities
)

def smart_search_with_fallback(query: str, db: Session):
    # Try 1: Full query with variants
    variants = expand_query(query)
    results = search_all_variants(variants, db)
    
    if results:
        return results
    
    # Try 2: Key entities only
    entities = extract_key_entities(query)
    entity_results = search_entities(entities, db)
    
    if entity_results:
        return entity_results
    
    # Try 3: Suggest related topics
    related = suggest_related_topics(query)
    return {
        "no_results": True,
        "suggestions": related,
        "message": f"No data found. Did you mean: {', '.join(related)}?"
    }
```

### Pattern 4: Query Confidence Scoring

```python
from app.services.query_expansion import (
    detect_intent,
    should_include_relaxed_search,
    expand_query
)

def query_confidence_score(query: str) -> dict:
    """Score query certainty and need for relaxation."""
    
    score = 0.0
    factors = {}
    
    # Factor 1: Query specificity (length)
    words = len(query.split())
    factors['specificity'] = min(words / 5, 1.0)  # Max at 5 words
    score += factors['specificity'] * 0.3
    
    # Factor 2: Has clear intent
    intent = detect_intent(query)
    factors['intent_clarity'] = 0.0 if intent == "general" else 1.0
    score += factors['intent_clarity'] * 0.3
    
    # Factor 3: Needs relaxation
    needs_relax = should_include_relaxed_search(query)
    factors['needs_relaxation'] = 0.5 if needs_relax else 1.0
    score += factors['needs_relaxation'] * 0.4
    
    return {
        "overall_score": round(score, 2),  # 0.0-1.0
        "factors": factors,
        "recommendation": "strict" if score > 0.6 else "relaxed"
    }

# Usage:
result = query_confidence_score("what is machine learning")
# Returns:
# {
#   "overall_score": 0.95,
#   "factors": {"specificity": 0.4, "intent_clarity": 1.0, "needs_relaxation": 1.0},
#   "recommendation": "strict"
# }
```

### Pattern 5: User-Specific Query Tuning

```python
class QueryTuner:
    """Learns user query patterns over time."""
    
    def __init__(self):
        self.user_queries = {}  # user_id -> [queries]
        self.working_variants = {}  # user_id -> {query -> best_variants}
    
    def track_query(self, user_id: str, query: str, success: bool):
        """Track whether a query variation worked for user."""
        if user_id not in self.user_queries:
            self.user_queries[user_id] = []
        
        self.user_queries[user_id].append({
            "query": query,
            "success": success,
            "timestamp": datetime.now()
        })
    
    def get_optimized_variants(self, user_id: str, query: str):
        """Return optimized variants based on user history."""
        if user_id in self.working_variants and query in self.working_variants[user_id]:
            # Return previously successful variants
            return self.working_variants[user_id][query]
        
        # Otherwise use standard expansion
        from app.services.query_expansion import expand_query
        return expand_query(query)
```

## Configuration Options

### Threshold Tuning

```python
# In .env file
RAG_MIN_SIMILARITY_FOR_CONTEXT=0.20        # Lower = more lenient
RAG_MIN_LEXICAL_OVERLAP_FOR_CONTEXT=0.08   # Lower = accept more
RAG_RELAXED_MIN_SIMILARITY_FOR_CONTEXT=0.12
RAG_RELAXED_MIN_LEXICAL_OVERLAP_FOR_CONTEXT=0.03
```

### Adding Custom Synonyms

```python
# In query_expansion.py, modify SYNONYMS dict:
SYNONYMS = {
    "your_term": ["expansion1", "expansion2", "expansion3"],
    "crypto": ["blockchain", "web3", "cryptocurrency"],
    # Add more as needed
}
```

### Adding Custom Intents

```python
# In query_expansion.py, modify INTENT_KEYWORDS:
INTENT_KEYWORDS = {
    "custom_intent": ["keyword1", "keyword2", "keyword3"],
    # In expand_query(), add:
    elif intent == "custom_intent":
        # Custom logic here
        pass
}
```

## Debugging & Monitoring

### Viewing Expansion Details

```python
from app.services.query_expansion import (
    expand_query,
    detect_intent,
    extract_key_entities
)

query = "what is macOS VM"

print(f"Query: {query}")
print(f"Intent: {detect_intent(query)}")
print(f"Variants: {expand_query(query)}")
print(f"Entities: {extract_key_entities(query)}")
```

### Checking Query Logs

```bash
# Monitor FastAPI logs for query expansion events
tail -f logs/app.log | grep "query_expansion"

# Look for these log markers:
# - "Query expansion performed"
# - "Variant search result"
# - "Threshold relaxation applied"
# - "Summary generated successfully"
```

### Testing Query Understanding

```bash
# Test endpoint
curl -X GET "http://localhost:8000/api/v1/summarize/topic" \
  -H "Content-Type: application/json" \
  --data-urlencode "topic=what is macOS VM" \
  --data-urlencode "limit=5"

# Check response fields:
# - query_expanded: true if variants were used
# - num_variants_tried: how many variants were searched
# - is_conversational: true if general message
```

## Performance Optimization

### Caching Query Expansions

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_expand_query(query: str) -> tuple:
    """Cache expansions for same queries."""
    return tuple(expand_query(query))
```

### Limiting Variant Searches

```python
# In summarize.py, reduce variant count for long queries:
if len(query.split()) > 5:
    variants = expand_query(query)[:3]  # Only 3 variants
else:
    variants = expand_query(query)  # Full expansion (up to 8)
```

### Parallel Variant Search

```python
# Already implemented in summarize.py endpoint:
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(search_chunks, db, variant)
        for variant in variants
    ]
    results = [f.result() for f in futures]
```

## Testing

### Unit Tests

```python
def test_intent_detection():
    assert detect_intent("what is AI") == "definition"
    assert detect_intent("how do I") == "how_to"
    assert detect_intent("compare") == "comparison"

def test_query_expansion():
    variants = expand_query("what is macOS VM")
    assert "macOS VM" in variants  # Original
    assert any("virtual machine" in v for v in variants)  # Synonym
    assert len(variants) <= 8  # Max variants

def test_entity_extraction():
    entities = extract_key_entities("what is neural networks")
    assert "neural" in entities
    assert "networks" in entities
```

### Integration Tests

```python
def test_end_to_end_query():
    response = client.get(
        "/api/v1/summarize/topic",
        params={"topic": "what is macOS VM", "limit": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query_expanded"] == True
    assert data["num_variants_tried"] > 1
    assert len(data["summary"]) > 0
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Too many results | Thresholds too low | Increase `rag_min_similarity_for_context` |
| No results found | Thresholds too high | Lower thresholds in config |
| Wrong results | Variants not targeted | Add to SYNONYMS dict |
| Slow queries | Too many variants | Reduce `expand_query` max from 8 to 5 |
| Query not understood | Intent not detected | Add keywords to `INTENT_KEYWORDS` |

## Next Steps

1. **Test the API:** Try various query types
2. **Monitor logs:** Watch for expansion patterns
3. **Tune thresholds:** Adjust based on your data
4. **Add domain terms:** Extend SYNONYMS for your domain
5. **Track metrics:** Monitor which queries work best
