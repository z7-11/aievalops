from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.project_repository import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


class ProjectCreateRequest(BaseModel):
    """
    创建项目的请求数据。
    """

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    target_url: str = Field(
        min_length=1,
        max_length=500,
    )


class ProjectUpdateRequest(BaseModel):
    """
    修改项目的请求数据。

    所有字段都是可选的，
    只修改传入的字段。
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    target_url: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )


class ProjectResponse(BaseModel):
    """
    项目响应数据。
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    description: str | None
    target_url: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_api(
    request: ProjectCreateRequest,
    database: DatabaseSession,
) -> ProjectResponse:
    project = create_project(
        database,
        name=request.name.strip(),
        description=(
            request.description.strip()
            if request.description
            else None
        ),
        target_url=request.target_url.strip(),
    )

    return project


@router.get(
    "",
    response_model=list[ProjectResponse],
)
def list_projects_api(
    database: DatabaseSession,
) -> list[ProjectResponse]:
    return list_projects(database)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
def get_project_api(
    project_id: int,
    database: DatabaseSession,
) -> ProjectResponse:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
def update_project_api(
    project_id: int,
    request: ProjectUpdateRequest,
    database: DatabaseSession,
) -> ProjectResponse:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    values = request.model_dump(
        exclude_unset=True,
    )

    for field_name, field_value in values.items():
        if isinstance(field_value, str):
            values[field_name] = field_value.strip()

    return update_project(
        database,
        project,
        values,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_api(
    project_id: int,
    database: DatabaseSession,
) -> None:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    delete_project(
        database,
        project,
    )
