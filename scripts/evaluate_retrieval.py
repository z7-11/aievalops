import argparse
import json
import re
from pathlib import Path
from time import perf_counter

from app.core.config import settings
from app.rag.embedding import LocalEmbeddingModel
from app.rag.vector_store import ChromaVectorStore, VectorSearchResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize(text: str) -> str:
    """忽略空格和换行后比较证据原文。"""
    return re.sub(r"\s+", "", text)


def count_hits(
    results: list[VectorSearchResult],
    expected_sources: set[str],
    evidence: list[str],
) -> tuple[int, int]:
    """统计命中的来源和原文证据。"""
    source_hits = len(expected_sources & {result.source for result in results})
    evidence_hits = sum(
        any(
            result.source in expected_sources and normalize(quote) in normalize(result.content)
            for result in results
        )
        for quote in evidence
    )
    return source_hits, evidence_hits


def main() -> None:
    parser = argparse.ArgumentParser(description="计算 RAG 检索召回率")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/evals/datasets/rag_cases.csv"),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=settings.rag_top_k,
    )
    parser.add_argument("--persist-dir", type=Path, default=Path(settings.rag_chroma_path))
    parser.add_argument("--collection", default=settings.rag_collection_name)
    parser.add_argument("--embedding-model", default=settings.rag_embedding_model)
    parser.add_argument("--min-score", type=float, default=settings.rag_vector_min_similarity_score)
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--overlap", type=int)
    parser.add_argument("--experiment-id")
    parser.add_argument("--output", type=Path, help="保存独立 JSON 报告；已有文件不会覆盖")
    args = parser.parse_args()

    if args.top_k < 1:
        raise ValueError("--top-k 必须大于 0")
    if not 0 <= args.min_score <= 1:
        raise ValueError("--min-score 必须在 0 到 1 之间")

    started_at = perf_counter()

    dataset_path = args.dataset
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path

    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"找不到评测集：{dataset_path}。请先确认第 10.10 步的 JSONL 文件路径"
        )

    chroma_path = args.persist_dir
    if not chroma_path.is_absolute():
        chroma_path = PROJECT_ROOT / chroma_path

    if not chroma_path.is_dir():
        raise FileNotFoundError(f"找不到 Chroma 索引目录：{chroma_path}")

    store = ChromaVectorStore(
        persist_dir=chroma_path,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
    )

    if store.collection.count() == 0:
        raise ValueError(f"Chroma 集合 {args.collection} 没有数据，请先构建索引")

    print(f"加载 Embedding 模型：{args.embedding_model}")
    embedding_model = LocalEmbeddingModel(model_name=args.embedding_model)

    source_hits = 0
    source_total = 0
    evidence_hits = 0
    evidence_total = 0
    raw_source_hits = 0
    raw_evidence_hits = 0
    evaluated_cases = 0
    skipped_cases = 0
    case_results: list[dict[str, object]] = []

    lines = dataset_path.read_text(encoding="utf-8-sig").splitlines()

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        try:
            case = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"评测集第 {line_number} 行不是合法 JSON：{error}") from error

        # 无依据问题用于后续“拒答评测”，不计入检索召回率。
        if case.get("should_refuse", False):
            skipped_cases += 1
            continue

        case_id = case["id"]
        question = case["question"]
        expected_sources = set(case["expected_sources"])
        evidence = case["evidence"]

        if not expected_sources or not evidence:
            raise ValueError(f"{case_id} 缺少 expected_sources 或 evidence")

        question_vector = embedding_model.encode_query(question)

        raw_results = store.query(
            query_embedding=question_vector,
            top_k=args.top_k,
        )

        # 与当前 RAG API 保持一致：过滤低于相似度阈值的结果。
        results = [result for result in raw_results if result.score >= args.min_score]

        current_source_hits, current_evidence_hits = count_hits(results, expected_sources, evidence)
        current_raw_source_hits, current_raw_evidence_hits = count_hits(
            raw_results, expected_sources, evidence
        )

        source_hits += current_source_hits
        source_total += len(expected_sources)
        evidence_hits += current_evidence_hits
        evidence_total += len(evidence)
        raw_source_hits += current_raw_source_hits
        raw_evidence_hits += current_raw_evidence_hits
        evaluated_cases += 1

        passed = current_source_hits == len(expected_sources) and current_evidence_hits == len(
            evidence
        )

        status = "PASS" if passed else "MISS"
        case_results.append(
            {
                "id": case_id,
                "question": question,
                "passed_after_threshold": passed,
                "source_hits": current_source_hits,
                "source_total": len(expected_sources),
                "evidence_hits": current_evidence_hits,
                "evidence_total": len(evidence),
                "raw_source_hits": current_raw_source_hits,
                "raw_evidence_hits": current_raw_evidence_hits,
                "retrieved": [
                    {
                        "file": result.source,
                        "score": result.score,
                        "chunk_id": result.chunk_id,
                        "passed_threshold": result.score >= args.min_score,
                    }
                    for result in raw_results
                ],
            }
        )
        print(
            f"{case_id} [{status}] "
            f"来源 {current_source_hits}/{len(expected_sources)}，"
            f"证据 {current_evidence_hits}/{len(evidence)}"
        )

    if evaluated_cases == 0:
        raise ValueError("没有可用于计算召回率的问答用例")

    print("\n===== 检索评测结果 =====")
    print(f"参与评测：{evaluated_cases} 条")
    print(f"跳过拒答用例：{skipped_cases} 条")
    print(f"Top K：{args.top_k}")
    print(f"相似度阈值：{args.min_score}")
    print(
        f"未过滤来源召回率@{args.top_k}："
        f"{raw_source_hits / source_total:.2%} "
        f"({raw_source_hits}/{source_total})"
    )
    print(
        f"未过滤证据召回率@{args.top_k}："
        f"{raw_evidence_hits / evidence_total:.2%} "
        f"({raw_evidence_hits}/{evidence_total})"
    )
    print(
        f"来源召回率@{args.top_k}：{source_hits / source_total:.2%} ({source_hits}/{source_total})"
    )
    print(
        f"证据召回率@{args.top_k}："
        f"{evidence_hits / evidence_total:.2%} "
        f"({evidence_hits}/{evidence_total})"
    )

    if args.output is not None:
        output_path = args.output
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "experiment_id": args.experiment_id,
            "dataset": str(dataset_path),
            "collection": args.collection,
            "embedding_model": args.embedding_model,
            "chunk_size": args.chunk_size,
            "overlap": args.overlap,
            "index_count": store.collection.count(),
            "top_k": args.top_k,
            "min_score": args.min_score,
            "evaluated_cases": evaluated_cases,
            "skipped_refusal_cases": skipped_cases,
            "metrics": {
                "raw_source_recall_at_k": raw_source_hits / source_total,
                "raw_evidence_recall_at_k": raw_evidence_hits / evidence_total,
                "source_recall_after_threshold_at_k": source_hits / source_total,
                "evidence_recall_after_threshold_at_k": evidence_hits / evidence_total,
            },
            "counts": {
                "raw_source_hits": raw_source_hits,
                "raw_evidence_hits": raw_evidence_hits,
                "source_hits": source_hits,
                "source_total": source_total,
                "evidence_hits": evidence_hits,
                "evidence_total": evidence_total,
            },
            "elapsed_seconds": round(perf_counter() - started_at, 2),
            "cases": case_results,
        }
        with output_path.open("x", encoding="utf-8") as report_file:
            json.dump(report, report_file, ensure_ascii=False, indent=2)
            report_file.write("\n")
        print(f"JSON 报告：{output_path}")


if __name__ == "__main__":
    main()
