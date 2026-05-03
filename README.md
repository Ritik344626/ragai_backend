# Backend - RAG Trends API

Basic FastAPI backend scaffold for ingesting open-source trend/news data and serving RAG endpoints.

## Prerequisites

- Python 3.10+
- PostgreSQL 12+ (running locally or remote)
- Redis 6+ (for Celery broker/result backend)

## 1) Create and activate virtual environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

## 3) Configure environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

## 4) Setup PostgreSQL Database

```bash
# Create database (if not exists)
psql -U postgres -c "CREATE DATABASE rag_trends_db;"

# Enable pgvector extension (safe to run multiple times)
psql -U postgres -d rag_trends_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Note: the app now attempts to create `DB_NAME` automatically at startup if it is missing and the configured user has permission.

## 5) Run development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app will auto-create tables on startup.

## 6) Run Celery worker (required for automated pipeline)

```bash
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo --concurrency=1
```

Note: `solo` pool is recommended on macOS for Torch/SentenceTransformer stability.

## 7) Run Celery Beat (cron automation every 30 minutes)

Enable in `.env`:

```env
CELERY_BEAT_ENABLED=true
CELERY_BEAT_CRON_MINUTE=*/30
CELERY_BEAT_CRON_HOUR=*
CELERY_BEAT_CRON_DAY_OF_WEEK=*
CELERY_BEAT_CRON_DAY_OF_MONTH=*
CELERY_BEAT_CRON_MONTH_OF_YEAR=*
CELERY_BEAT_AUTO_LIMIT=15
```

Then run:

```bash
celery -A app.celery_app.celery_app beat --loglevel=info
```

## 8) Open docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Current API Routes

### Health & Root
- `GET /` root message
- `GET /api/v1/health` health check

### Sources (preview)
- `GET /api/v1/sources` list available free sources
- `GET /api/v1/sources/{source_id}/preview?limit=5` preview items from a source

### Ingestion (save to database)
- `POST /api/v1/ingest/fetch-and-save/{source_id}` fetch items and save to DB with dedup
- `GET /api/v1/ingest/items?source_id=xxx&limit=20` retrieve saved items from DB
- `POST /api/v1/ingest/auto/{source_id}?limit=15` queue automated pipeline (fetch->save->extract->index)
- `POST /api/v1/ingest/auto-all?limit=15` queue automated pipeline for all configured sources
- `POST /api/v1/ingest/auto-process-pending?limit=100` process existing unprocessed items
- `GET /api/v1/ingest/tasks/{task_id}` check Celery task state/result

### Summarization (AI-powered with Gemini)
- `GET /api/v1/summarize/topic?topic=...&limit=5` search and generate AI summary using Gemini

Grounding behavior:
- The assistant only answers from retrieved indexed evidence.
- Hybrid relevance filtering is applied (semantic + lexical).
- If evidence is weak/insufficient, it abstains instead of hallucinating.

## Setup Gemini API (Required for Summarization)

1. Get Gemini API key:
   - Go to https://aistudio.google.com/
   - Click "Get API Key"
   - Create new API key for your project
   - Copy the key

2. Add to .env:
   ```
   GEMINI_API_KEY=your_copied_api_key_here
   ```

3. Test:
   ```
   # After ingesting and indexing items, try:
   curl "http://localhost:8000/api/v1/summarize/topic?topic=AI+trends&limit=5"
   ```

### RAG (chunk, embed, search)
- `POST /api/v1/rag/index/{source_item_id}` chunk and embed a source item into PostgreSQL (idempotent)
- `GET /api/v1/rag/search?query=AI+trends&limit=5` semantic search over indexed chunks

## Automated Pipeline

`POST /api/v1/ingest/auto/{source_id}` runs this in background:
1. Fetch source data (RSS/HN/Google Trends)
2. Save new items to `source_items` with URL dedup
3. Extract full article body from each new URL into `raw_content`
4. Chunk and embed content
5. Save vectors in pgvector and mark `source_items.is_processed=true`

The indexing step is idempotent:
- Already processed items are skipped.
- Existing chunk hashes are skipped (prevents duplicate chunk rows).

## Database Schema

### source_items table
- `id` - Primary key
- `source_id` - News/trend source identifier
- `title` - Item title or keyword
- `url` - Item URL
- `url_hash` - SHA256 hash (unique, prevents duplicates)
- `published_at` - Optional publish timestamp
- `summary` - Short description or snippet
- `raw_content` - Full content (optional)
- `is_processed` - Flag for RAG pipeline
- `created_at` - When inserted
- `updated_at` - Last update time

Indexes on: `source_id`, `url_hash`, `is_processed`, `(source_id, published_at)`

### chunks table
- `id` - Primary key
- `source_item_id` - Foreign key to source_items
- `chunk_index` - Position in original text
- `text` - Chunk content
- `chunk_hash` - SHA256 of chunk text
- `source_id` - Source identifier for filtering
- `published_at` - Inherited from source
- `url` - URL for citation/reference
- `is_indexed` - Flag indicating vector DB indexing
- `created_at` - When created
- `updated_at` - Last update

Indexes on: `source_item_id`, `chunk_hash`, `source_id`, `is_indexed`

### Vector Store (PostgreSQL Arrays)
- Column: `embedding` (384 dimensions from all-MiniLM-L6-v2)
- Stored directly in chunks table
- Type: `vector(384)` (pgvector)
- Distance metric: cosine distance in SQL (`<=>`) via ORM helper
- Index: HNSW index created automatically on startup
- No separate infrastructure needed
