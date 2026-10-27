"""运行第 10.13 步的六组 Chunk Size × Embedding 检索实验。"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BGE_MODEL = "BAAI/bge-small-zh-v1.5"
MINILM_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class Experiment:
    name: str
    chunk_size: int
    overlap: int
    embedding_model: str


EXPERIMENTS = (
    Experiment("A1", 300, 50, BGE_MODEL),
    Experiment("A2", 500, 80, BGE_MODEL),
    Experiment("A3", 800, 120, BGE_MODEL),
    Experiment("B1", 300, 50, MINILM_MODEL),
    Experiment("B2", 500, 80, MINILM_MODEL),
    Experiment("B3", 800, 120, MINILM_MODEL),
)


def run_command(arguments: list[str], environment: dict[str, str]) -> None:
    print("\n运行：", " ".join(arguments), flush=True)
    subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="比较六组 RAG 检索配置")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/evals/datasets/rag_cases.csv"),
    )
    parser.add_argument("--top-k", type=int, default=settings.rag_top_k)
    parser.add_argument("--min-score", type=float, default=settings.rag_vector_min_similarity_score)
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=[experiment.name for experiment in EXPERIMENTS],
        default=[experiment.name for experiment in EXPERIMENTS],
        help="只运行指定组；默认运行 A1 到 B3",
    )
    args = parser.parse_args()

    dataset_path = args.dataset
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path
    if not dataset_path.is_file():
        raise FileNotFoundError(f"评测集不存在：{dataset_path}")

    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_dir = PROJECT_ROOT / "results" / "experiments" / run_id
    report_dir.mkdir(parents=True, exist_ok=False)
    persist_dir = PROJECT_ROOT / "storage" / "chroma"
    results: list[dict[str, object]] = []
    failure: str | None = None

    try:
        for experiment in EXPERIMENTS:
            if experiment.name not in args.groups:
                continue

            collection = f"rag_{experiment.name.lower()}_{run_id}"
            report_path = report_dir / f"{experiment.name}.json"
            environment = os.environ.copy()

            if experiment.embedding_model == MINILM_MODEL:
                # 将新模型缓存放在项目的忽略目录内，不改动用户主目录。
                environment["HF_HOME"] = str(PROJECT_ROOT / "storage" / "huggingface")

            # 两个模型都已缓存；避免每次加载都等待联网探测超时。
            environment["HF_HUB_OFFLINE"] = "1"

            print(
                f"\n===== {experiment.name}: chunk={experiment.chunk_size}, "
                f"overlap={experiment.overlap}, model={experiment.embedding_model} =====",
                flush=True,
            )

            run_command(
                [
                    sys.executable,
                    "-m",
                    "scripts.build_rag_index",
                    "--persist-dir",
                    str(persist_dir),
                    "--collection",
                    collection,
                    "--embedding-model",
                    experiment.embedding_model,
                    "--chunk-size",
                    str(experiment.chunk_size),
                    "--overlap",
                    str(experiment.overlap),
                ],
                environment,
            )

            run_command(
                [
                    sys.executable,
                    "-m",
                    "scripts.evaluate_retrieval",
                    "--dataset",
                    str(dataset_path),
                    "--persist-dir",
                    str(persist_dir),
                    "--collection",
                    collection,
                    "--embedding-model",
                    experiment.embedding_model,
                    "--chunk-size",
                    str(experiment.chunk_size),
                    "--overlap",
                    str(experiment.overlap),
                    "--experiment-id",
                    experiment.name,
                    "--top-k",
                    str(args.top_k),
                    "--min-score",
                    str(args.min_score),
                    "--output",
                    str(report_path),
                ],
                environment,
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            results.append(
                {
                    "experiment_id": experiment.name,
                    "chunk_size": experiment.chunk_size,
                    "overlap": experiment.overlap,
                    "embedding_model": experiment.embedding_model,
                    "collection": collection,
                    "report": str(report_path),
                    "index_count": report["index_count"],
                    "metrics": report["metrics"],
                }
            )
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        failure = str(error)
        raise
    finally:
        summary = {
            "run_id": run_id,
            "dataset": str(dataset_path),
            "top_k": args.top_k,
            "min_score": args.min_score,
            "completed_groups": len(results),
            "requested_groups": args.groups,
            "failure": failure,
            "experiments": results,
        }
        summary_path = report_dir / "summary.json"
        with summary_path.open("x", encoding="utf-8") as summary_file:
            json.dump(summary, summary_file, ensure_ascii=False, indent=2)
            summary_file.write("\n")
        print(f"\n汇总报告：{summary_path}", flush=True)


if __name__ == "__main__":
    main()
