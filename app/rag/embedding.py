from sentence_transformers import SentenceTransformer


class LocalEmbeddingModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        vectors = self.model.encode_document(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def encode_query(
        self,
        query: str,
    ) -> list[float]:
        vector = self.model.encode_query(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()