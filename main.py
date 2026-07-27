import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from beanie import init_beanie
from pymongo import AsyncMongoClient
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from langfuse import get_client
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

from utils.env import settings
from utils.logger import get_logger
from utils.custom_errors import APIError
from routes.default import app as default_router
from routes.github import app as github_router
from routes.project import app as project_router
from routes.agent import app as agent_router
from models.project import Project

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to MongoDB")
    app.state.mongo_client = AsyncMongoClient(settings.MONGO_DB_URI)
    await init_beanie(database=app.state.mongo_client.backend, document_models=[Project])
    logger.info("Connecting to Redis")
    app.state.redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    logger.info("creating httpx client")
    app.state.httpx_client = httpx.AsyncClient()

    logger.info("Connecting to langfuse")
    langfuse = get_client()

    if langfuse.auth_check():
        logger.info("langfuse ok")
    else:
        logger.info("langfuse bad")

    logger.info("instrumenting code with openai agents instrumenter")
    OpenAIAgentsInstrumentor().instrument()

    logger.info("Startup complete")
    yield
    logger.info("Shutting down — closing MongoDB, Redis and HTTP connections")
    await app.state.mongo_client.close()
    await app.state.redis_client.aclose()
    await app.state.httpx_client.aclose()

    logger.info("flushing the langfuse logs")
    langfuse.flush()

    logger.info("Shutdown complete")


app = FastAPI(title="Coding Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(default_router)
app.include_router(github_router)
app.include_router(project_router)
app.include_router(agent_router)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    logger.exception("APIError on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={"error": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
