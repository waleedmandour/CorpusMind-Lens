"""Project CRUD (§9.1). Unlimited projects, bounded by disk."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..main import get_store

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    name: str
    description: str = ""


@router.get("/projects")
async def list_projects() -> list[dict]:
    return [asdict(p) for p in get_store().list_projects()]


@router.post("/projects", status_code=201)
async def create_project(payload: ProjectIn) -> dict:
    p = get_store().create_project(payload.name, payload.description)
    return asdict(p)


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    p = get_store().get_project(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return asdict(p)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    if not get_store().delete_project(project_id):
        raise HTTPException(404, "Project not found")
    return {"deleted": project_id}
