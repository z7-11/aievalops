from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


def create_project(
    database: Session,
    *,
    name: str,
    description: str | None,
    target_url: str,
) -> Project:
    """
    创建一个项目。
    """

    project = Project(
        name=name,
        description=description,
        target_url=target_url,
    )

    database.add(project)
    database.commit()
    database.refresh(project)

    return project


def list_projects(
    database: Session,
) -> list[Project]:
    """
    查询所有项目。
    """

    statement = select(Project).order_by(
        Project.id
    )

    return list(
        database.scalars(statement).all()
    )


def get_project(
    database: Session,
    project_id: int,
) -> Project | None:
    """
    根据 ID 查询项目。
    """

    return database.get(
        Project,
        project_id,
    )


def update_project(
    database: Session,
    project: Project,
    values: dict[str, object],
) -> Project:
    """
    修改项目信息。
    """

    for field_name, field_value in values.items():
        setattr(
            project,
            field_name,
            field_value,
        )

    database.commit()
    database.refresh(project)

    return project


def delete_project(
    database: Session,
    project: Project,
) -> None:
    """
    删除项目。

    项目下的测试用例、评测记录等关联数据，
    会按照模型中的级联规则处理。
    """

    database.delete(project)
    database.commit()