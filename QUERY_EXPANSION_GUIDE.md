# Query Expansion & Conversational Handling Fixes

## Issues Solved

### Issue #1: General Messages Not Responding
**Problem:** User queries like "hello", "how are you", etc. returned "no data found"
**Root Cause:** These queries have no semantic match in indexed data, so reranking filters them out
**Solution:** Added `is_general_question()` detection that serves conversational responses without searching

**Example:**
```
User: "Hello"
Before: "I do not have enough relevant indexed data..."
After: "Hi! I'm a RAG Assistant. I can help answer questions about trends and news..."
```

### Issue #2: Query Variation Sensitivity
**Problem:** "macOS VM" finds results, but "what is macOS VM" returns no data
**Root Cause:** Query reformulation changes semantic embedding; no query expansion
**Solution:** Added `expand_query()` that generates multiple query forms and searches all variants

**Example:**
```
Original query: "what is macOS VM"
Expanded to:
  1. "what is macOS VM" (original)
  2. "macOS VM" (QA words removed)
  3. "macOS VM definition" (statement form)
  4. Content tokens: "macOS vm performance" (noun phrases)
  
Result: Searches all variants, deduplicates chunks, finds matches!
```

## Implementation Details

### 1. New Service: `app/services/query_expansion.py`

**Functions:**
- `is_general_question(query)` → Detects "hello", "thanks", "how are you", etc.
- `get_general_response(key)` → Canned conversational responses
- `expand_query(query)` → Generates 3-4 query variations
- `should_relax_thresholds(query)` → Identifies queries needing lenient matching

**Conversational Patterns Handled:**
```python
"hello", "hi", "how are you", "what can you do", 
"who are you", "thanks", "goodbye"
```

### 2. Updated: `app/api/routes/summarize.py`

**New Flow:**
```
1. Check if general_question → return conversational response
2. Expand query into 3-4 variants
3. Search with ALL variants (deduplicate results)
4. If no results AND query is short/open-ended → relax thresholds (fallback mode)
5. Summarize results OR return "no data" message
```

**New Response Fields:**
```json
{
  "query": "what is macOS VM",
  "summary": "...",
  "sources": [...],
  "chunk_count": 3,
  "is_grounded": true,
  "is_conversational": false,
  "query_expanded": true,
  "num_variants_tried": 4
}
```

## Configuration Tuning

The behavior is controlled by settings in `app/core/config.py`:

```python
# Existing RAG thresholds (adjust these for more/less strict retrieval)
rag_min_similarity_for_context: float = 0.22  # Semantic similarity threshold
rag_min_lexical_overlap_for_context: float = 0.10  # Lexical overlap threshold
rag_enable_relaxed_fallback: bool = True  # Allow fallback mode
```

**To be more lenient (find more results):**
- Lower `rag_min_similarity_for_context` (e.g., 0.20 → 0.15)
- Lower `rag_min_lexical_overlap_for_context` (e.g., 0.10 → 0.05)

**To be more strict (find only high-confidence results):**
- Increase `rag_min_similarity_for_context` (e.g., 0.22 → 0.30)
- Increase `rag_min_lexical_overlap_for_context` (e.g., 0.10 → 0.20)

## Test Cases

### Conversational Queries (No DB Search)
```bash
curl "http://localhost:8000/api/v1/summarize/topic?topic=hello"
# Returns: Hi! I'm a RAG Assistant...

curl "http://localhost:8000/api/v1/summarize/topic?topic=what+can+you+do"
# Returns: I can search through indexed trends...
```

### Query Variations (Multi-Search)
```bash
# Before: "what is macOS VM" returned no data
# After: Finds results because "macOS VM" variant is searched
curl "http://localhost:8000/api/v1/summarize/topic?topic=what+is+macOS+VM&limit=5"

# Also works now:
curl "http://localhost:8000/api/v1/summarize/topic?topic=tell+me+about+AI+trends"
curl "http://localhost:8000/api/v1/summarize/topic?topic=how+do+neural+networks+work"
```

## Performance Impact

- **Query expansion:** ~10-30ms additional (parallel searches on multiple variants)
- **General question detection:** <1ms (regex match)
- **Deduplication:** O(n) where n = chunks found (negligible)

## Known Limitations

1. **Conversational context not preserved:** Each query is independent (no multi-turn memory)
2. **Query expansion is heuristic-based:** May generate unhelpful variants for complex queries
3. **Hard-coded conversational responses:** Not based on indexed data (intentional)
4. **No external knowledge fallback:** Still requires indexed data for substantive answers

## Future Improvements

1. **Multi-turn conversation:** Track message history per session
2. **LLM-based query expansion:** Use Gemini to generate better query variants
3. **Contextual threshold adjustment:** Dynamically adjust thresholds based on query type
4. **Hybrid keyword search:** Add BM25 lexical search alongside semantic search
5. **User feedback loop:** Learn which variants work best for similar queries

## Migration Notes

No database changes required. This is a pure service-layer enhancement.
To activate:
1. Pull the latest changes (includes `query_expansion.py` and updated `summarize.py`)
2. Restart the FastAPI server
3. Test with both general queries and query variations

## Monitoring

To track effectiveness, watch for these metrics:

```python
# In logs, you'll see:
query_expanded=true  # When query variants were used
num_variants_tried=4  # How many variants were searched
is_conversational=true  # For general questions
relevance_mode=relaxed  # When thresholds were relaxed
```
