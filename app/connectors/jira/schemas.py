from pydantic import BaseModel, Field
from typing import Optional


class JiraImportRequest(BaseModel):
    """
    MVP: Tek proje (project_key) için Jira'dan raw rows basar.
    Auth: Şimdilik basic token (email + api_token) ile.
    """
    base_url: str = Field(..., description="Örn: https://your-domain.atlassian.net")
    email: str = Field(..., description="Jira Cloud e-mail (token ile birlikte kullanılır)")
    api_token: str = Field(..., description="Jira API token")
    project_key: str = Field(..., description="Örn: THOR")

    # MVP'yi bozmadan ileriye dönük alanlar (şimdilik kullanılmayacak)
    jql: Optional[str] = Field(None, description="Opsiyonel JQL override (MVP'de yok sayılabilir)")
    max_issues: Optional[int] = Field(500, description="MVP için güvenlik limiti")
    include_worklogs: Optional[bool] = Field(True, description="Worklog çekilsin mi (MVP: True)")


class JiraImportResponse(BaseModel):
    batch_id: int
    status: str  # started / completed / completed_err

    # Görünür MVP telemetrisi (kullanıcı ne olduğunu anlasın)
    raw_rows_written: int = 0
    errors_logged: int = 0

    message: str = ""