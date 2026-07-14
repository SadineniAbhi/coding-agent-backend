from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PATH_PREFIX: str
    OPENAI_API_KEY: str
    AUTH0_DOMAIN: str
    AUTH0_AUDIENCE: str
    MONGO_DB_URI: str
    REDIS_URL: str
    SANDBOX_EXPIRY_TIME_SEC: int
    SANDBOX_IMAGE: str
    AGENT_MAX_TURNS: int = 30
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str

    model_config = {"env_file": ".env"}


settings = Settings() # type: ignore
