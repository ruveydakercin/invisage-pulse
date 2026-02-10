from pydantic import BaseModel, Field
from typing import Optional

class JiraImportRequest(BaseModel):
    project_key: str = Field(..., min_length=1)
    jql: Optional[str] = None
    max_issues: int = 50
    include_worklogs: bool = False

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