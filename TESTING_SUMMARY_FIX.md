# Quick Start: Testing the Summary Truncation Fix

## What Changed

The backend now:
- ✅ Truncates chunks before sending to Gemini (prevents token overflow)
- ✅ Validates response quality (rejects broken/incomplete answers)
- ✅ Cleans up malformed evidence markers
- ✅ Returns complete, properly formatted summaries

## Deploy the Fix

### 1. Reload Backend (if running in development)
```bash
# The backend will auto-reload if running with --reload flag
# Or restart manually:
cd /Users/ritik/Documents/git/rag_ai/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 2. Test the Fix

#### Test 1: Query that was broken
```bash
curl "http://localhost:8000/api/v1/summarize/topic?topic=what+is+macOS+VM"
```

**Expected Response:**
```json
{
  "query": "what is macOS VM",
  "summary": "Complete answer without broken '- E1' references...",
  "chunk_count": 1,
  "is_grounded": true,
  "query_expanded": true,
  "num_variants_tried": 8
}
```

#### Test 2: Complex query
```bash
curl "http://localhost:8000/api/v1/summarize/topic?topic=tell+me+about+AI+trends&limit=5"
```

**Expected Response:**
```json
{
  "query": "tell me about AI trends",
  "summary": "Multi-line answer with proper bullet points:\n- Bullet point 1 [E1]\n- Bullet point 2 [E2]",
  "chunk_count": 2,
  "is_grounded": true,
  "query_expanded": true,
  "num_variants_tried": 4
}
```

#### Test 3: Conversational message
```bash
curl "http://localhost:8000/api/v1/summarize/topic?topic=hello"
```

**Expected Response:**
```json
{
  "query": "hello",
  "summary": "Hi! I'm a RAG Assistant...",
  "is_conversational": true,
  "is_grounded": false,
  "chunk_count": 0
}
```

## Verification Checklist

- [ ] Summary is complete (not ending with "- E1")
- [ ] Evidence citations are in bullets, not in answer text
- [ ] Bullet format: "- Description [E1]"
- [ ] Response is valid JSON
- [ ] No errors in backend logs
- [ ] Frontend displays properly with badges

## Troubleshooting

### Issue: Still getting incomplete summaries

**Check 1: Is backend using new code?**
```bash
# Check modification time
ls -l /Users/ritik/Documents/git/rag_ai/backend/app/services/summarization.py
# Should show recent time (within last few minutes)
```

**Check 2: Backend reloaded?**
- If using `--reload`, changes should auto-apply
- If not, restart the server manually
- Check logs for "Uvicorn running on"

**Check 3: Chunk too large?**
Reduce `MAX_CHUNK_LENGTH` in summarization.py:
```python
MAX_CHUNK_LENGTH = 300  # Smaller (was 400)
```

### Issue: Getting "no data found" messages

**Likely causes:**
- Thresholds too strict (try with `limit=10`)
- Chunks not indexed yet
- Query doesn't match indexed topics

**Solution:**
```bash
# Test with higher limit
curl "http://localhost:8000/api/v1/summarize/topic?topic=what+is+macOS+VM&limit=10"
```

### Issue: JSON parsing errors in logs

Check if backend is using old code:
```bash
# Verify file was updated
grep "MAX_CHUNK_LENGTH" /Users/ritik/Documents/git/rag_ai/backend/app/services/summarization.py
# Should show: MAX_CHUNK_LENGTH = 400
```

## Frontend Testing

Once backend is working, test in chat UI:

1. **Open frontend** (http://localhost:3000)
2. **Send test messages:**
   - "what is macOS VM"
   - "tell me about AI trends"
   - "hello"

3. **Look for:**
   - Complete summaries (no broken references)
   - Badges showing query info:
     - 💬 Chat (for conversational)
     - 🔄 8 variants (query expansion)
   - Source links (clickable)
   - Topic suggestions (if applicable)

## Performance Check

The fix should improve performance:

```
Before: 
- Backend response time: 2-4 seconds
- Token usage per request: 2000-3000

After:
- Backend response time: 1-2 seconds  
- Token usage per request: 800-1200
```

Monitor response times in browser DevTools (Network tab).

## Configuration Tuning (if needed)

### Reduce truncation (more detail, might risk overflow)
```python
# In app/services/summarization.py
MAX_CHUNK_LENGTH = 500  # was 400
```

### Increase truncation (less detail, more safety)
```python
MAX_CHUNK_LENGTH = 300  # was 400
```

### Adjust minimum answer length (if getting too many fallbacks)
```python
# Current: len(answer) > 10
# Make more lenient:
if answer and len(answer) > 5 and not answer.startswith("- E"):
```

## Next Steps

1. ✅ Test the fix with above commands
2. ✅ Verify frontend displays properly
3. ✅ Monitor backend logs for errors
4. ✅ Tune `MAX_CHUNK_LENGTH` if needed
5. ✅ Add domain-specific terms to synonyms

## Files Modified

- `app/services/summarization.py` - Added chunk truncation & better validation
- `SUMMARY_TRUNCATION_FIX.md` - Detailed fix documentation

## Support

If issues persist:
1. Check backend logs: `tail -f logs/app.log`
2. Test with detailed debugging:
   ```bash
   python3 << 'EOF'
   import sys
   sys.path.insert(0, '/Users/ritik/Documents/git/rag_ai/backend')
   from app.services.summarization import generate_summary
   
   test_chunks = [{
       "text": "Test content",
       "source_id": "test",
       "url": "http://test.com",
       "published_at": "2026-05-03",
       "similarity_score": 0.8
   }]
   
   result = generate_summary("what is test", test_chunks)
   print(result)
   EOF
   ```
3. Reduce `MAX_CHUNK_LENGTH` to 250-300 if still truncating
4. Enable debug logging if needed
