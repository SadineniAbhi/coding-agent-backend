import time

import jwt
import httpx
from pymongo import AsyncMongoClient

from utils.env import settings
from utils.logger import get_logger
from utils.redis_utils import RedisUtils
from utils.custom_errors import GitHubAPIError, InstallationNotFoundError, KeyNotFoundError

logger = get_logger(__name__)


def _generate_app_jwt() -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": settings.GITHUB_APP_ID}
    with open(settings.GITHUB_APP_PRIVATE_KEY_PATH, "rb") as f:
        private_key = f.read()
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(
    user_id: str, mongo_client: AsyncMongoClient, redis_utils: RedisUtils
) -> str:
    try:
        return await redis_utils.get_if_exists(f"github:installation_token:{user_id}")
    except KeyNotFoundError:
        pass

    user_doc = await mongo_client.backend.user.find_one({"user_id": user_id})
    if not user_doc or not user_doc.get("installation_id"):
        raise InstallationNotFoundError(f"No GitHub installation found for user '{user_id}'", status_code=404)

    installation_id = user_doc["installation_id"]
    headers = {
        "Authorization": f"Bearer {_generate_app_jwt()}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers=headers,
            )
        except httpx.RequestError:
            raise GitHubAPIError("Failed to reach GitHub API", status_code=502)

    if resp.status_code != 201:
        logger.error("Unexpected GitHub API status %s: %s", resp.status_code, resp.text)
        raise GitHubAPIError(f"GitHub API returned unexpected status {resp.status_code}", status_code=502)

    token = resp.json()["token"]

    await redis_utils.set(f"github:installation_token:{user_id}", token, ttl=2400)
    logger.info("Stored GitHub installation token for user %s", user_id)
    return token
