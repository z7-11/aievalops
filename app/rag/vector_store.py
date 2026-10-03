from dataclasses import dataclass
from pathlib import Path

import chromadb

from app.rag.document_loader import DocumentChunk


@dataclass(frozen=True)
class VectorSearchResult:
    """Chroma 返回的一条知识库片段。"""

    source: str
    content: str
    score: float
    chunk_index: int
    page: int | None
    chunk_id: str


class ChromaVectorStore:
    """负责保存文档向量、查询相近文档片段。"""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        embedding_model: str,
    ) -> None:
        persist_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # PersistentClient 会将数据保存在指定目录。
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
        )

        # 一个 Collection 可以理解成一组独立的向量索引。
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={
                "hnsw": {
                    "space": "cosine",
                }
            },
            metadata={
                "embedding_model": embedding_model,
            },
        )

        # 如果同名 Collection 已存在，Chroma 会返回旧的。
        # 检查模型名称，防止把不同模型生成的向量混在一起。
        saved_metadata = self.collection.metadata or {}
        saved_model = saved_metadata.get("embedding_model")

        if saved_model != embedding_model:
            raise ValueError(
                f"Collection {collection_name} 使用的 "
                f"Embedding 模型是 {saved_model}，"
                f"当前请求使用 {embedding_model}。"
                "请换一个 Collection 名称。"
            )

        # 后面的 score = 1 - distance 只适用于余弦距离。
        hnsw_config = self.collection.configuration.get("hnsw") or {}

        if hnsw_config.get("space") != "cosine":
            raise ValueError(
                f"Collection {collection_name} 不是 cosine 距离配置。请换一个新的 Collection 名称。"
            )

    def upsert(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        """写入片段；相同 ID 再次写入时更新记录。"""

        if not chunks:
            raise ValueError("chunks 不能为空")

        if len(chunks) != len(embeddings):
            raise ValueError("文档片段数与向量数不一致")

        if any(not chunk.chunk_id for chunk in chunks):
            raise ValueError("每个文档片段都必须有 chunk_id")

        dimension = len(embeddings[0])

        if dimension == 0:
            raise ValueError("向量不能为空")

        if any(len(embedding) != dimension for embedding in embeddings):
            raise ValueError("所有向量的维度必须一致")

        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "source": chunk.source,
                    # Chroma 元数据中统一用 0 表示无页码。
                    "page": (chunk.page if chunk.page is not None else 0),
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[VectorSearchResult]:
        """根据问题向量，返回最相近的 top_k 个片段。"""

        if not query_embedding:
            raise ValueError("query_embedding 不能为空")

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        stored_count = self.collection.count()

        if stored_count == 0:
            return []

        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(
                top_k,
                stored_count,
            ),
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        documents = response["documents"]
        metadatas = response["metadatas"]
        distances = response["distances"]

        if documents is None or metadatas is None or distances is None:
            raise RuntimeError("Chroma 查询结果缺少必要字段")

        results: list[VectorSearchResult] = []

        # 因为只查询了一个问题，所以读取下标 [0]。
        for chunk_id, content, metadata, distance in zip(
            response["ids"][0],
            documents[0],
            metadatas[0],
            distances[0],
            strict=True,
        ):
            if content is None or metadata is None:
                raise RuntimeError("Chroma 查询结果缺少正文或来源信息")

            stored_page = int(metadata["page"])

            # cosine distance 越小越相近；
            # 转成便于阅读的分数，越大表示越相近。
            score = max(
                0.0,
                min(
                    1.0,
                    1.0 - float(distance),
                ),
            )

            results.append(
                VectorSearchResult(
                    source=str(metadata["source"]),
                    content=content,
                    score=round(score, 4),
                    chunk_index=int(metadata["chunk_index"]),
                    page=(stored_page if stored_page != 0 else None),
                    chunk_id=chunk_id,
                )
            )

        return results
