import argparse
from pathlib import Path
from time import perf_counter

from app.rag.document_loader import load_documents
from app.rag.embedding import LocalEmbeddingModel
from app.rag.vector_store import ChromaVectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="读取客服知识库并构建 Chroma 向量索引")

    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        default=Path("knowledge"),
        help="PDF 和 Markdown 所在目录",
    )

    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=Path("storage/chroma"),
        help="Chroma 数据保存目录",
    )

    parser.add_argument(
        "--collection",
        default="customer_service_bge_500_v1",
        help="本次实验使用的 Chroma 集合名称",
    )

    parser.add_argument(
        "--embedding-model",
        default="BAAI/bge-small-zh-v1.5",
        help="将文本转换为向量的模型",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="每个片段最多多少字符",
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=80,
        help="相邻片段重叠多少字符",
    )

    args = parser.parse_args()
    started_at = perf_counter()

    # 第一步：读取 Markdown/PDF，并切分为文档片段。
    chunks = load_documents(
        knowledge_dir=args.knowledge_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    file_count = len({chunk.source for chunk in chunks})

    print(f"读取文件数：{file_count}")
    print(f"生成片段数：{len(chunks)}")
    print(f"Chunk Size：{args.chunk_size}")
    print(f"Overlap：{args.overlap}")

    # 第二步：打开本地 Chroma。
    store = ChromaVectorStore(
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
    )

    # 已有数据时停止，避免旧片段留在索引里。
    existing_count = store.collection.count()

    if existing_count > 0:
        raise RuntimeError(
            f"Collection {args.collection} 已有 "
            f"{existing_count} 条记录。"
            "请为本次构建指定新的 --collection 名称。"
        )

    # 第三步：加载 Embedding 模型，并将所有片段转成向量。
    print(f"正在加载模型：{args.embedding_model}")

    embedding_model = LocalEmbeddingModel(model_name=args.embedding_model)

    texts = [chunk.content for chunk in chunks]

    print("正在生成文档向量……")

    embeddings = embedding_model.encode_documents(texts)

    print(f"向量数量：{len(embeddings)}")
    print(f"向量维度：{len(embeddings[0])}")

    # 第四步：把片段、向量和来源信息一起存入 Chroma。
    print("正在写入 Chroma……")

    store.upsert(
        chunks=chunks,
        embeddings=embeddings,
    )

    stored_count = store.collection.count()
    elapsed_seconds = perf_counter() - started_at

    print()
    print("索引构建完成")
    print(f"Collection：{args.collection}")
    print(f"Chroma 记录数：{stored_count}")
    print(f"耗时：{elapsed_seconds:.2f} 秒")

    if stored_count != len(chunks):
        raise RuntimeError("写入数量与文档片段数量不一致，请检查 Chroma 数据")


if __name__ == "__main__":
    main()
