"""RAG 文档、向量和检索单元测试；不加载真实 Embedding 模型。"""

from pathlib import Path

import numpy as np
import pytest

from app.rag import embedding as embedding_module
from app.rag.document_loader import (
    build_chunk_id,
    load_documents,
    load_markdown_documents,
    split_text,
)
from app.rag.vector_retriever import VectorRetriever
from app.rag.vector_store import ChromaVectorStore, VectorSearchResult

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"


@pytest.mark.unit
def test_load_markdown_document() -> None:
    chunks = load_markdown_documents(KNOWLEDGE_DIR, chunk_size=200, overlap=20)
    refund_chunks = [chunk for chunk in chunks if chunk.source == "refund.md"]

    assert refund_chunks
    assert refund_chunks[0].page is None
    assert "退款规则" in refund_chunks[0].content


@pytest.mark.unit
def test_load_pdf_document_with_page_number() -> None:
    chunks = load_documents(KNOWLEDGE_DIR, chunk_size=500, overlap=80)
    pdf_chunks = [chunk for chunk in chunks if chunk.source == "raw/privacy.pdf"]

    assert pdf_chunks
    assert pdf_chunks[0].page == 1
    assert pdf_chunks[0].chunk_id
    assert pdf_chunks[0].content.strip()


@pytest.mark.unit
def test_split_text_keeps_overlap() -> None:
    chunks = split_text("ABCDEFGHIJKL", chunk_size=5, overlap=2)

    assert chunks[0] == "ABCDE"
    assert chunks[1] == "DEFGH"
    assert all(left[-2:] == right[:2] for left, right in zip(chunks, chunks[1:], strict=False))


@pytest.mark.unit
def test_chunk_id_is_stable() -> None:
    first = build_chunk_id("refund.md", None, 0, "七天内可退款")
    repeated = build_chunk_id("refund.md", None, 0, "七天内可退款")
    changed = build_chunk_id("refund.md", None, 0, "十五天内可退款")

    assert first == repeated
    assert first != changed


@pytest.mark.unit
def test_embedding_dimension_is_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            assert model_name == "fake-embedding"

        def encode_document(self, texts: list[str], **_: object) -> np.ndarray:
            return np.asarray([[1.0, 0.0, 0.0] for _ in texts])

        def encode_query(self, query: str, **_: object) -> np.ndarray:
            assert query == "退款"
            return np.asarray([1.0, 0.0, 0.0])

    monkeypatch.setattr(embedding_module, "SentenceTransformer", FakeSentenceTransformer)
    model = embedding_module.LocalEmbeddingModel("fake-embedding")

    documents = model.encode_documents(["退款规则", "物流规则"])
    query = model.encode_query("退款")

    assert len(documents) == 2
    assert len(query) == 3
    assert all(len(vector) == len(query) for vector in documents)


@pytest.mark.unit
def test_chroma_returns_expected_source() -> None:
    class FakeCollection:
        def count(self) -> int:
            return 1

        def query(self, **kwargs: object) -> dict:
            assert kwargs["query_embeddings"] == [[1.0, 0.0]]
            assert kwargs["n_results"] == 1
            return {
                "ids": [["refund-1"]],
                "documents": [["普通商品签收后七天内可退款。"]],
                "metadatas": [[{"source": "refund.md", "page": 0, "chunk_index": 0}]],
                "distances": [[0.1]],
            }

    store = object.__new__(ChromaVectorStore)
    store.collection = FakeCollection()
    results = store.query([1.0, 0.0], top_k=1)

    assert len(results) == 1
    assert results[0].source == "refund.md"
    assert results[0].chunk_id == "refund-1"
    assert results[0].page is None
    assert results[0].score == 0.9


@pytest.mark.unit
def test_vector_retriever_rejects_blank_query() -> None:
    class FakeEmbedder:
        def encode_query(self, query: str) -> list[float]:
            raise AssertionError("空问题不能进入 Embedding")

    class FakeStore:
        def query(self, query_embedding: list[float], top_k: int) -> list[VectorSearchResult]:
            raise AssertionError("空问题不能进入 Chroma")

    retriever = VectorRetriever(FakeEmbedder(), FakeStore())

    with pytest.raises(ValueError, match="query 不能为空"):
        retriever.search("   ")
