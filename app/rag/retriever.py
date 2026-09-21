from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag.document_loader import DocumentChunk


@dataclass(frozen=True)
class RetrievalResult:
    """
    一条检索结果。
    """

    source: str
    content: str
    score: float
    chunk_index: int


class TfidfRetriever:
    """
    基于 TF-IDF 的文本检索器。
    """

    def __init__(
        self,
        chunks: list[DocumentChunk],
    ) -> None:
        if not chunks:
            raise ValueError("chunks 不能为空")

        self.chunks = chunks

        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            lowercase=True,
        )

        contents = [
            chunk.content
            for chunk in self.chunks
        ]

        self.document_matrix = (
            self.vectorizer.fit_transform(contents)
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """
        根据问题返回最相关的文本片段。
        """

        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("query 不能为空")

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_vector = self.vectorizer.transform(
            [normalized_query]
        )

        scores = cosine_similarity(
            query_vector,
            self.document_matrix,
        )[0]

        ranked_indexes = scores.argsort()[::-1]

        results: list[RetrievalResult] = []

        for index in ranked_indexes[:top_k]:
            chunk = self.chunks[index]

            results.append(
                RetrievalResult(
                    source=chunk.source,
                    content=chunk.content,
                    score=round(
                        float(scores[index]),
                        4,
                    ),
                    chunk_index=chunk.chunk_index,
                )
            )

        return results