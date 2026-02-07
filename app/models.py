from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import relationship
from app.db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    work_items = relationship("WorkItem", back_populates="project", cascade="all, delete-orphan")


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    external_key = Column(String(100), nullable=False)
    title = Column(String(300), nullable=False)
    status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="work_items")
    time_entries = relationship("TimeEntry", back_populates="work_item", cascade="all, delete-orphan")
    cost_entries = relationship("CostEntry", back_populates="work_item", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    source = Column(String(30), nullable=False)
    external_id = Column(String(100), nullable=False)
    display_name = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    time_entries = relationship("TimeEntry", back_populates="resource", cascade="all, delete-orphan")
    cost_entries = relationship("CostEntry", back_populates="resource", cascade="all, delete-orphan")


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    work_item = relationship("WorkItem", back_populates="time_entries")
    resource = relationship("Resource", back_populates="time_entries")


class CostEntry(Base):
    __tablename__ = "cost_entries"

    id = Column(Integer, primary_key=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="TRY")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    work_item = relationship("WorkItem", back_populates="cost_entries")
    resource = relationship("Resource", back_populates="cost_entries")


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default="csv")  # csv/jira/ado vs.
    status = Column(String(20), nullable=False, default="received")  # received|processing|completed|failed
    filename = Column(String(255), nullable=True)
    mapping_json = Column(Text, nullable=True)  # şimdilik saklıyoruz (audit/debug)
    total_rows = Column(Integer, nullable=False, default=0)
    success_rows = Column(Integer, nullable=False, default=0)
    error_rows = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    raw_rows = relationship("ImportRawRow", back_populates="batch", cascade="all, delete-orphan")
    errors = relationship("ImportError", back_populates="batch", cascade="all, delete-orphan")


class ImportRawRow(Base):
    __tablename__ = "import_raw_row"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)  # CSV satır no (1’den başlat)
    raw_json = Column(Text, nullable=False)       # Dict’i json string olarak sakla
    normalized_hint = Column(String(50), nullable=True)  # time_entry / cost_entry vb

    row_status = Column(String(10), nullable=False, default="PENDING")  # PENDING|VALID|INVALID

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    batch = relationship("ImportBatch", back_populates="raw_rows")


class ImportError(Base):
    __tablename__ = "import_error"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False)
    raw_row_id = Column(Integer, ForeignKey("import_raw_row.id", ondelete="CASCADE"), nullable=True)

    severity = Column(String(10), nullable=False, default="ERROR")  # ERROR / WARN
    error_code = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)

    field_name = Column(String(100), nullable=True)
    raw_value = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    batch = relationship("ImportBatch", back_populates="errors")