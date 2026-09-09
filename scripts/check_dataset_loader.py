from pathlib import Path

from app.services.dataset_service import load_dataset

dataset_path = Path(
    "data/examples/customer_service_cases.csv"
)

records = load_dataset(dataset_path)

print(f"成功加载 {len(records)} 条测试用例")

for record in records:
    print(
        f"{record.case_id} | "
        f"{record.priority} | "
        f"{record.expected_keywords}"
    )