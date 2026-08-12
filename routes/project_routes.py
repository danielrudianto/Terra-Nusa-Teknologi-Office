from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from controllers.project_controller import ProjectController
from schemas.project_schema import (
    ProjectCreate,
    ProjectUpdate,
    ContractCreate,
    ContractUpdate,
)
from utils.permission import require

router = APIRouter()


def _bereskan(result: dict):
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.get("/")
async def get_projects(
    request: Request,
    current_user: Annotated[dict, Depends(require("project", "read"))],
    sortBy: str = Query(None),
    sortByDirection: str = Query("asc"),
    isActive: bool | None = Query(None),
    isCancelled: bool | None = Query(None),
):
    return _bereskan(
        await ProjectController.get_projects(
            request.query_params.get("keyword"),
            isActive,
            isCancelled,
            int(request.query_params.get("page", 1)),
            int(request.query_params.get("pageSize", 10)),
            sortBy,
            sortByDirection,
        )
    )


@router.post("/")
async def create_project(
    body: ProjectCreate,
    current_user: Annotated[dict, Depends(require("project", "create"))],
):
    return _bereskan(
        await ProjectController.create_project(body.model_dump(), current_user["id"])
    )


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: Annotated[dict, Depends(require("project", "read"))],
):
    """Rincian proyek beserta seluruh baris kontraknya."""
    return _bereskan(await ProjectController.get_project(project_id))


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    current_user: Annotated[dict, Depends(require("project", "update"))],
):
    return _bereskan(
        await ProjectController.update_project(
            project_id, body.model_dump(exclude_unset=True), current_user["id"]
        )
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: Annotated[dict, Depends(require("project", "delete"))],
):
    return _bereskan(
        await ProjectController.delete_project(project_id, current_user["id"])
    )


# ---- Kontrak --------------------------------------------------------------
#
# Menambah atau mengubah baris kontrak memakai izin `update` pada modul
# proyek, bukan `create`: yang sedang diubah adalah nilai kontrak sebuah
# proyek yang sudah ada, bukan membuat proyek baru.


@router.post("/{project_id}/contracts")
async def add_contract(
    project_id: int,
    body: ContractCreate,
    current_user: Annotated[dict, Depends(require("project", "update"))],
):
    return _bereskan(
        await ProjectController.add_contract(
            project_id, body.model_dump(), current_user["id"]
        )
    )


@router.put("/contracts/{contract_id}")
async def update_contract(
    contract_id: int,
    body: ContractUpdate,
    current_user: Annotated[dict, Depends(require("project", "update"))],
):
    return _bereskan(
        await ProjectController.update_contract(
            contract_id, body.model_dump(exclude_unset=True), current_user["id"]
        )
    )


@router.delete("/contracts/{contract_id}")
async def delete_contract(
    contract_id: int,
    current_user: Annotated[dict, Depends(require("project", "delete"))],
):
    return _bereskan(
        await ProjectController.delete_contract(contract_id, current_user["id"])
    )
