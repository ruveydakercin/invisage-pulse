from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "invisage-pulse"
    app_env: str = "local"

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    class Config:
        env_file = ".env"


settings = Settings()
