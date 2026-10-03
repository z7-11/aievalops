"""把问题编码和 Chroma 查询封装为可独立测试的检索步骤。"""

from typing import Protocol

from app.rag.vector_store import ChromaVectorStore, VectorSearchResult


class QueryEmbedder(Protocol):
    def encode_query(self, query: str) -> list[float]: ...


class VectorRetriever:
    def __init__(self, embedding_model: QueryEmbedder, store: ChromaVectorStore) -> None:
        self.embedding_model = embedding_model
        self.store = store

    def search(self, query: str, top_k: int = 3) -> list[VectorSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query 不能为空")
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")
        query_embedding = self.embedding_model.encode_query(normalized_query)
        return self.store.query(query_embedding=query_embedding, top_k=top_k)
