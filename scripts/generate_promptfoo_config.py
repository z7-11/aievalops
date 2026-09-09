from pathlib import Path

from app.services.dataset_service import load_dataset
from app.services.promptfoo_config_service import (
    build_promptfoo_config,
    write_promptfoo_config,
)


def main() -> None:
    dataset_path = Path(
        "data/examples/customer_service_cases.csv"
    )

    output_path = Path(
        "evals/generated_promptfooconfig.yaml"
    )

    test_cases = load_dataset(dataset_path)

    config = build_promptfoo_config(
        test_cases=test_cases,
        target_url="http://127.0.0.1:3001/api/chat",
    )

    generated_path = write_promptfoo_config(
        config=config,
        output_path=output_path,
    )

    print(f"成功生成配置文件：{generated_path}")
    print(f"共生成 {len(test_cases)} 条测试用例")


if __name__ == "__main__":
    main()