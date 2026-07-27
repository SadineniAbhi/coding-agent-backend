from typing import cast
from redis.asyncio import Redis
from utils.logger import get_logger
from utils.custom_errors import KeyAlreadyExistsError, KeyNotFoundError


class RedisUtils:
    '''
        This is a utility class for redis
    '''

    def __init__(self, client: Redis) -> None:
        self.logger = get_logger(__name__)
        self.client = client


    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self.client.set(key, value, ex=ttl)


    async def set_if_not_exists(self, key: str, value: str, ttl: int | None = None) -> None:
        was_set = await self.client.set(key, value, nx=True, ex=ttl)
        if not was_set:
            raise KeyAlreadyExistsError(f"Key '{key}' already exists", status_code=409)


    async def get_if_exists(self, key: str, ttl: int | None = None) -> str:
        value = await self.client.getex(key, ex=ttl) if ttl else await self.client.get(key)
        if value is None:
            raise KeyNotFoundError(f"Key '{key}' not found", status_code=404)
        return cast(str, value)


    async def delete_key(self, key: str) -> None:
        await self.client.delete(key)
