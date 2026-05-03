import os

from sentence_transformers import SentenceTransformer

from app.core.config import settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", settings.tokenizers_parallelism)
os.environ.setdefault("OMP_NUM_THREADS", str(settings.omp_num_threads))
os.environ.setdefault("MKL_NUM_THREADS", str(settings.mkl_num_threads))

# Initialize model once globally for efficiency
_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model."""
    global _model
    if _model is None:
        # Optional torch safety tuning for constrained worker environments.
        try:
            import torch

            torch.set_num_threads(max(1, settings.omp_num_threads))
        except Exception:
            pass
        # Using a lightweight but good-quality open model
        # ~110M params, 384 dimensions
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """
    Convert text to embedding vector using SentenceTransformers.
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding as list of floats
    """
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=False)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convert multiple texts to embeddings (batch mode is faster).
    
    Args:
        texts: List of texts to embed
    
    Returns:
        List of embeddings
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=False)
    return [e.tolist() for e in embeddings]
