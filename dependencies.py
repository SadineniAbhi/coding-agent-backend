from functools import lru_cache
from fastapi import Request
from pymongo import AsyncMongoClient
from clients.kuberentes import KubernetesClient

@lru_cache
def get_kubernetes_client() -> KubernetesClient:
    return KubernetesClient()


def get_mongo_client(request: Request) -> AsyncMongoClient:
    return request.app.state.mongo_client

