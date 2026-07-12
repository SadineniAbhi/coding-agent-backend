from fastapi import APIRouter, Depends
from utils.logger import get_logger
from utils.env import settings
from utils.auth import validate_token
from payloads.project import CreateProjectRequest
from service import project_service

app = APIRouter(prefix=settings.PATH_PREFIX, tags=["Project"])
logger = get_logger(__name__)


@app.get("/projects")
async def list_projects(claims=Depends(validate_token)):
    return await project_service.s_list_projects(user_id=claims["sub"])


@app.post("/project")
async def create_project(body: CreateProjectRequest, claims=Depends(validate_token)):
    return await project_service.s_create_project(body, user_id=claims["sub"])
