import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.llm_client import (  # noqa: E402
    create_llm_client,
)
from app.rag.service import RAGService  # noqa: E402


def main() -> None:
    rag_service = RAGService(
        knowledge_dir=PROJECT_ROOT / "knowledge",
    )

    question = "商品签收后 5 天可以退款吗？"

    prompt = rag_service.build_prompt(
        question=question,
        top_k=3,
    )

    print("========== Prompt ==========")
    print(prompt)

    client = create_llm_client()

    answer = client.generate(prompt)

    print()
    print("========== Ollama 回答 ==========")
    print(answer)


if __name__ == "__main__":
    main()
