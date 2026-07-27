from utils.env import settings
from utils.logger import get_logger
from fastapi import APIRouter, Depends
from utils.auth import validate_token
from utils.redis_utils import RedisUtils
from dependencies import get_redis_utils, get_mongo_client
from service import github as github_service

app = APIRouter(prefix=settings.PATH_PREFIX, tags=["GitHub"])
logger = get_logger(__name__)


@app.post("/connect/github")
async def connect_github(
    claims=Depends(validate_token),
    redis_utils: RedisUtils = Depends(get_redis_utils),
    mongo_client=Depends(get_mongo_client),
):
    return await github_service.s_connect_github(
        user_id=claims["sub"], redis_utils=redis_utils, mongo_client=mongo_client
    )


@app.get("/github/setup")
async def set_up(
    installation_id: str,
    state: str,
    setup_action: str,
    redis_utils: RedisUtils = Depends(get_redis_utils),
    mongo_client=Depends(get_mongo_client),
):
    return await github_service.s_setup_github(
        installation_id=installation_id,
        state=state,
        setup_action=setup_action,
        redis_utils=redis_utils,
        mongo_client=mongo_client,
    )


@app.post("/github/list-repos")
async def list_repos(
    claims=Depends(validate_token),
    redis_utils: RedisUtils = Depends(get_redis_utils),
    mongo_client=Depends(get_mongo_client),
):
    return await github_service.s_list_repos(
        user_id=claims["sub"], mongo_client=mongo_client, redis_utils=redis_utils
    )
