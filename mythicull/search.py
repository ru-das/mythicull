import numpy as np

from mythicull import embed


def rank(project_id: str, embedder: embed.Embedder, query: str, k: int, allowed: set[str] | None = None) -> list[str]:
    """Photo ids best-first for `query`. Scores only order results within this one query."""
    ids, matrix = embed.load_store(project_id, embedder.model_id)
    keep = [i for i, pid in enumerate(ids) if allowed is None or pid in allowed]
    if not keep:
        return []
    q = embedder.encode_text([query])[0]
    scores = matrix[keep] @ q  # vectors are unit length, so this is cosine similarity
    order = np.argsort(-scores, kind="stable")[:k]
    return [ids[keep[i]] for i in order]
