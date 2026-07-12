from fastapi import APIRouter, Depends
from utils.env import settings
from utils.logger import get_logger
from utils.auth import validate_token

app = APIRouter(prefix=settings.PATH_PREFIX, tags=["Health"])
logger = get_logger(__name__)

@app.get("/health")
async def health():
    logger.info("GET /health")
    return {"status": "ok"}


@app.get("/health/auth")
async def health_auth(_=Depends(validate_token)):
    return {"status": "ok"}
