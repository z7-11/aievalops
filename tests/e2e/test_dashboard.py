from uuid import uuid4

from playwright.sync_api import Page, expect


def test_dashboard_can_create_project(page: Page) -> None:
    page.goto("http://127.0.0.1:3001/ui")

    expect(
        page.get_by_role("heading", name="AIEvalOps")
    ).to_be_visible()

    project_name = f"电商客服测试-{uuid4().hex[:8]}"

    page.get_by_label("项目名称").fill(project_name)
    page.get_by_label("目标地址").fill(
        "http://127.0.0.1:3001/api/chat"
    )

    page.get_by_role("button", name="保存").click()

    project_card = page.get_by_role("article").filter(
        has_text=project_name,
    )
    expect(project_card).to_be_visible()
