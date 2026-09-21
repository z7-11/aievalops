from typing import Any

import pytest
from fastapi.testclient import TestClient


def create_project(
    client: TestClient,
) -> int:
    """
    创建测试项目，并返回项目 ID。
    """

    response = client.post(
        "/api/projects",
        json={
            "name": "数据库测试项目",
            "description": "用于数据库接口测试",
            "target_url": (
                "http://127.0.0.1:3001/api/chat"
            ),
        },
    )

    assert response.status_code == 201

    response_body: dict[str, Any] = (
        response.json()
    )

    return response_body["id"]


def create_case_payload(
    case_id: str = "refund_001",
) -> dict[str, Any]:
    """
    创建一条测试用例请求数据。
    """

    return {
        "case_id": case_id,
        "module": "refund",
        "priority": "P0",
        "question": "商品签收后多久可以退款",
        "expected_keywords": [
            "7天",
            "订单详情页",
        ],
        "forbidden_keywords": [
            "3天",
        ],
        "max_latency_ms": 1000,
        "security_category": "functional",
    }


def test_create_project_success(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "客服接口测试项目",
            "description": "测试项目创建功能",
            "target_url": (
                "http://127.0.0.1:3001/api/chat"
            ),
        },
    )

    assert response.status_code == 201

    response_body = response.json()

    assert response_body["id"] > 0
    assert response_body["name"] == (
        "客服接口测试项目"
    )
    assert response_body["target_url"] == (
        "http://127.0.0.1:3001/api/chat"
    )


def test_empty_project_name_returns_422(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "",
            "description": "项目名称为空",
            "target_url": (
                "http://127.0.0.1:3001/api/chat"
            ),
        },
    )

    assert response.status_code == 422


def test_get_nonexistent_project_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/projects/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "项目不存在"
    )


def test_import_test_cases_success(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json={
            "cases": [
                create_case_payload(),
            ],
        },
    )

    assert response.status_code == 201

    response_body = response.json()

    assert len(response_body) == 1
    assert response_body[0]["case_id"] == (
        "refund_001"
    )
    assert response_body[0]["project_id"] == (
        project_id
    )


def test_duplicate_case_id_returns_409(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    payload = {
        "cases": [
            create_case_payload(
                "duplicate_001"
            ),
        ],
    }

    first_response = client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json=payload,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json=payload,
    )

    assert second_response.status_code == 409
    assert "case_id" in (
        second_response.json()["detail"]
    )


def test_duplicate_cases_in_one_request_roll_back(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json={
            "cases": [
                create_case_payload(
                    "same_001"
                ),
                create_case_payload(
                    "same_001"
                ),
            ],
        },
    )

    assert response.status_code == 409

    list_response = client.get(
        f"/api/projects/{project_id}/test-cases"
    )

    assert list_response.status_code == 200
    assert list_response.json() == []


def test_list_and_get_test_case(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json={
            "cases": [
                create_case_payload(
                    "query_001"
                ),
            ],
        },
    )

    list_response = client.get(
        f"/api/projects/{project_id}/test-cases"
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/projects/{project_id}/test-cases/query_001"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["case_id"] == (
        "query_001"
    )


def test_delete_project_returns_404_afterwards(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    import_response = client.post(
        f"/api/projects/{project_id}/test-cases/import",
        json={
            "cases": [
                create_case_payload(
                    "delete_001"
                ),
            ],
        },
    )

    assert import_response.status_code == 201

    delete_response = client.delete(
        f"/api/projects/{project_id}"
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/projects/{project_id}"
    )

    assert get_response.status_code == 404


def test_delete_nonexistent_test_case_returns_404(
    client: TestClient,
) -> None:
    project_id = create_project(client)

    response = client.delete(
        f"/api/projects/{project_id}/test-cases/not_found"
    )

    assert response.status_code == 404


def test_session_is_closed_after_generator_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db import session as database_session

    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    fake_session = FakeSession()

    monkeypatch.setattr(
        database_session,
        "SessionLocal",
        lambda: fake_session,
    )

    session_generator = (
        database_session.get_db()
    )

    returned_session = next(
        session_generator
    )

    assert returned_session is fake_session
    assert fake_session.closed is False

    session_generator.close()

    assert fake_session.closed is True