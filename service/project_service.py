import uuid
from pymongo import AsyncMongoClient
from models.project import Project
from utils.custom_errors import InstallationNotFoundError, ProjectError
from utils.logger import get_logger
from payloads.project import CreateProjectRequest

logger = get_logger(__name__)


async def get_project_by_id(project_id: str, user_id: str) -> Project:
    project = await Project.find_one(Project.project_id == project_id)

    if not project:
        logger.warning("No project found with id '%s'", project_id)
        raise ProjectError(f"Project '{project_id}' not found", status_code=404)

    if project.user_id != user_id:
        logger.warning("User is unauthorized to access project '%s'", project_id)
        raise ProjectError(f"Unauthorized to access project '{project_id}'", status_code=401)

    return project

async def s_list_projects(user_id: str) -> dict:
    projects = await Project.list_projects(user_id)
    logger.info("Listed %d projects for user '%s'", len(projects), user_id)
    return {"projects": [p.model_dump() for p in projects]}

async def s_create_project(body: CreateProjectRequest, user_id: str, mongo_client: AsyncMongoClient) -> dict:
    user_doc = await mongo_client.backend.user.find_one({"user_id": user_id})
    if not user_doc or not user_doc.get("github_login"):
        raise InstallationNotFoundError(f"No GitHub installation found for user '{user_id}'", status_code=404)

    project = await Project.create_project(
        name=body.name,
        user_id=user_id,
        project_id=str(uuid.uuid4()),
        github_user_name=user_doc["github_login"],
        github_repo_url=body.github_repo_url,
        description=body.description,
    )
    logger.info("Created project '%s' for user '%s'", project.project_id, user_id)
    return {"project_id": project.project_id, "name": project.name}
