from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "invisage-pulse"
    app_env: str = "local"

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    database_url: str

    # Jira Connector settings
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None

    class Config:
        env_file = ".env"
        extra = "forbid"


settings = Settings()