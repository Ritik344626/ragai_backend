import tiktoken


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[str]:
    """
    Split text into overlapping chunks using token-based splitting.
    
    Args:
        text: Text to chunk
        chunk_size: Max tokens per chunk
        overlap: Token overlap between chunks
    
    Returns:
        List of text chunks
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    
    chunks: list[str] = []
    start_idx = 0
    
    while start_idx < len(tokens):
        end_idx = min(start_idx + chunk_size, len(tokens))
        chunk_tokens = tokens[start_idx:end_idx]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        
        # Move start to next chunk position minus overlap
        start_idx = end_idx - overlap
        if start_idx >= len(tokens) - overlap:
            break
    
    return chunks
