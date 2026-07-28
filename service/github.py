import httpx
import uuid
from pymongo import AsyncMongoClient
from fastapi.responses import RedirectResponse
from utils.env import settings
from utils.github import get_installation_token, get_installation_account_login
from utils.logger import get_logger
from utils.redis_utils import RedisUtils
from utils.custom_errors import (
    InvalidGitHubToken,
    GitHubAPIError,
    KeyNotFoundError,
)

logger = get_logger(__name__)


async def s_connect_github(
    user_id: str, redis_utils: RedisUtils, mongo_client: AsyncMongoClient
) -> dict:
    user_doc = await mongo_client.backend.user.find_one({"user_id": user_id})
    if user_doc and user_doc.get("installation_id"):
        logger.info("User %s already has a GitHub installation", user_id)
        return {"status": "ok"}

    state = str(uuid.uuid4())
    await redis_utils.set_if_not_exists(state, user_id)

    install_url = f"https://github.com/apps/{settings.GITHUB_APP_NAME}/installations/new?state={state}"
    logger.info("Redirecting user %s to GitHub App installation", user_id)
    return {"redirect_url": install_url}


async def s_setup_github(
    installation_id: str,
    state: str,
    setup_action: str,
    redis_utils: RedisUtils,
    mongo_client: AsyncMongoClient,
) -> RedirectResponse:

    try:
        user_id = await redis_utils.get_if_exists(state)
    except KeyNotFoundError:
        logger.warning("GitHub install callback with unknown or expired state")
        raise InvalidGitHubToken("Invalid or expired state", status_code=400)

    await redis_utils.delete_key(state)

    account_login = await get_installation_account_login(installation_id)

    await mongo_client.backend.user.update_one(
        {"user_id": user_id},
        {"$set": {"installation_id": installation_id, "github_login": account_login}},
        upsert=True,
    )
    logger.info(
        "Linked GitHub installation %s for user %s (setup_action=%s)", installation_id, user_id, setup_action
    )
    return RedirectResponse(settings.FRONTEND_ORIGIN)



async def s_list_repos(user_id: str, mongo_client: AsyncMongoClient, redis_utils: RedisUtils) -> list[dict]:
    token = await get_installation_token(user_id, mongo_client, redis_utils)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    repos = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers=headers,
                    params={"per_page": 100, "page": page},
                )
            except httpx.RequestError:
                raise GitHubAPIError("Failed to reach GitHub API", status_code=502)

            if resp.status_code == 401:
                logger.warning("GitHub token rejected with 401 while listing repos")
                raise InvalidGitHubToken("Invalid or expired GitHub token", status_code=401)

            if resp.status_code != 200:
                logger.error("Unexpected GitHub API status %s: %s", resp.status_code, resp.text)
                raise GitHubAPIError(f"GitHub API returned unexpected status {resp.status_code}", status_code=502)

            page_repos = resp.json()["repositories"]
            if not page_repos:
                break

            repos.extend(page_repos)
            page += 1

    logger.info("Listed %d repos", len(repos))
    return [{"full_name": r["full_name"], "url": r["html_url"]} for r in repos]

