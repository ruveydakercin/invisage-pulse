from sqlalchemy import Column, Integer, String, DateTime, Text, func
from app.db import Base


class PulseEvent(Base):
    __tablename__ = "pulse_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)      # ör: "manual", "jira", "slack"
    title = Column(String(200), nullable=False)
    payload = Column(Text, nullable=True)          # şimdilik basit tutuyoruz

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
