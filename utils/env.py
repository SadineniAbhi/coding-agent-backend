from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PATH_PREFIX: str
    OPENAI_API_KEY: str
    AUTH0_DOMAIN: str
    AUTH0_AUDIENCE: str
    MONGO_DB_URI: str

    model_config = {"env_file": ".env"}


settings = Settings() # type: ignore
