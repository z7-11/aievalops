from pathlib import Path

from app.rag.document_loader import (
    DocumentChunk,
    load_markdown_documents,
)
from app.rag.llm_client import build_rag_prompt
from app.rag.retriever import (
    RetrievalResult,
    TfidfRetriever,
)


class RAGService:
    """
    知识库检索服务。
    """

    def __init__(
        self,
        knowledge_dir: Path,
    ) -> None:
        self.knowledge_dir = knowledge_dir

        self.chunks: list[DocumentChunk] = (
            load_markdown_documents(
                knowledge_dir=knowledge_dir,
            )
        )

        self.retriever = TfidfRetriever(
            chunks=self.chunks,
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, object]]:
        """
        搜索知识库，并返回字典格式结果。
        """

        results: list[RetrievalResult] = (
            self.retriever.search(
                query=query,
                top_k=top_k,
            )
        )

        return [
            {
                "source": result.source,
                "content": result.content,
                "score": result.score,
            }
            for result in results
        ]

    def build_prompt(
        self,
        question: str,
        top_k: int = 3,
    ) -> str:
        """
        检索知识后，生成给大模型使用的 Prompt。
        """

        results = self.retriever.search(
            query=question,
            top_k=top_k,
        )

        return build_rag_prompt(
            question=question,
            results=results,
        )