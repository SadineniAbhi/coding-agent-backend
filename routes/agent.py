import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from utils.env import settings
from utils.logger import get_logger
from utils.auth import validate_token
from utils.custom_errors import APIError
from payloads.agent import Execute
from dependencies import get_mongo_client, get_sandbox
from service.agent import run_agent, get_session_messages
from service.sandbox import Sandbox

app = APIRouter(prefix=settings.PATH_PREFIX, tags=["Agent"])
logger = get_logger(__name__)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.post("/agent/{project_id}/run")
async def run(
    project_id: str,
    task: Execute,
    claims=Depends(validate_token),
    mongo_client=Depends(get_mongo_client),
    sandbox: Sandbox = Depends(get_sandbox),
):
    async def generate():
        try:
            async for chunk in run_agent(project_id, task.task, claims["sub"], mongo_client, sandbox):
                yield _sse({"type": "token", "content": chunk})
        except APIError as e:
            logger.exception("Agent run failed")
            yield _sse({"type": "error", "message": str(e)})
        except Exception:
            logger.exception("Agent run failed")
            yield _sse({"type": "error", "message": "An unexpected error occurred"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/agent/{project_id}/messages")
async def messages(project_id: str, claims=Depends(validate_token), mongo_client=Depends(get_mongo_client)):
    return await get_session_messages(project_id, claims["sub"], mongo_client)
