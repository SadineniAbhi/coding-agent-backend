from urllib.parse import urlparse

import httpx
from clients.kuberentes import KubernetesClient
from models.project import Project
from utils.env import settings
from utils.logger import get_logger
from utils.retry import retry_async
from utils.custom_errors import CommandFailed, InfraNotFoundError, ProjectError

logger = get_logger(__name__)


class Sandbox:

    def __init__(self, k8s_client: KubernetesClient, httpx_client: httpx.AsyncClient) -> None:
        self.k8s_client = k8s_client
        self.httpx_client = httpx_client

    @staticmethod
    def _repo_dir_name(repo_url: str) -> str:
        return urlparse(repo_url).path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")

    async def _create_sandbox(self, project_id: str, project: Project) -> dict:
        logger.info("Creating sandbox for project '%s'", project_id)
        await self.k8s_client.create_infra(project_id, settings.SANDBOX_IMAGE)
        logger.info("Sandbox infra ready for project '%s'", project_id)

        clone_url = project.github_repo_url.replace("https://", f"https://x:{project.github_pat_token}@")
        logger.info("Cloning repo '%s' into sandbox for project '%s'", project.github_repo_url, project_id)
        res = await self._run(project_id, f"git clone {clone_url}", dir="")
        logger.info("Repo cloned for project '%s'", project_id)

        logger.info("setting the remote")
        repo_dir = self._repo_dir_name(project.github_repo_url)
        authenticated_url = project.github_repo_url.replace(
            "https://", f"https://{project.github_user_name}:{project.github_pat_token}@"
        )
        res = await self._run(project_id, f"git remote set-url origin {authenticated_url}", dir=repo_dir)
        logger.info("remote set successfully")
        return res

    async def _check_sandbox_exist(self, project_id: str) -> bool:
        try:
            await self.k8s_client.get_infra(project_id)
            logger.debug("Sandbox already exists for project '%s'", project_id)
            return True
        except InfraNotFoundError:
            logger.debug("No existing sandbox for project '%s'", project_id)
            return False

    async def _run(self, project_id: str, command: str, dir: str) -> dict:
        url = self.k8s_client.service_url(project_id)
        logger.debug("Running command for project '%s' in dir '%s': %s", project_id, dir, command)

        async def _post() -> httpx.Response:
            return await self.httpx_client.post(
                f"{url}/sandbox/api/execute",
                json={
                    "command": command,
                    "dir": dir,
                },
            )

        try:
            response = await retry_async(_post, exceptions=(httpx.RequestError,))
        except httpx.RequestError as e:
            logger.error("Failed to reach sandbox for project '%s': %s", project_id, e)
            raise CommandFailed(f"Unable to reach sandbox for project '{project_id}'", status_code=502)

        return response.json()

    async def execute(self, project_id: str, command: str) -> dict:
        logger.info("Executing command for project '%s'", project_id)
        project = await Project.find_project(project_id)
        if project is None:
            logger.error("Project '%s' not found", project_id)
            raise ProjectError(f"Project '{project_id}' not found", status_code=404)

        if not await self._check_sandbox_exist(project_id):
            res = await self._create_sandbox(project_id, project)
            if res.get("status", "") == "error":
                return res

        repo_dir = self._repo_dir_name(project.github_repo_url)
        return await self._run(project_id, command, dir=repo_dir)
