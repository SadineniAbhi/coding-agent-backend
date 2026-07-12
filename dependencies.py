import httpx
from fastapi import Depends, Request
from pymongo import AsyncMongoClient
from redis.asyncio import Redis
from clients.kuberentes import KubernetesClient
from service.sandbox import Sandbox
from utils.redis_utils import RedisUtils

def get_kubernetes_client() -> KubernetesClient:
    return KubernetesClient()


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.httpx_client


def get_sandbox(
    k8s_client: KubernetesClient = Depends(get_kubernetes_client),
    httpx_client: httpx.AsyncClient = Depends(get_httpx_client),
) -> Sandbox:
    return Sandbox(k8s_client, httpx_client)


def get_mongo_client(request: Request) -> AsyncMongoClient:
    return request.app.state.mongo_client


def get_redis_client(request: Request) -> Redis:
    return request.app.state.redis_client


def get_redis_utils(redis_client: Redis = Depends(get_redis_client)) -> RedisUtils:
    return RedisUtils(redis_client)

