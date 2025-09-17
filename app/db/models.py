from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CodeSystem(Base):
    __tablename__ = "codesystems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cs_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(512), unique=True)
    version: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    title: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="active")
    content: Mapped[dict] = mapped_column(JSON)  # full FHIR JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConceptMap(Base):
    __tablename__ = "conceptmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cm_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(512), unique=True)
    version: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Mapping(Base):
    __tablename__ = "mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(256), index=True)
    source_code: Mapped[str] = mapped_column(String(128), index=True)
    target_system: Mapped[str] = mapped_column(String(256), index=True)
    target_code: Mapped[str] = mapped_column(String(128), index=True)
    equivalence: Mapped[str] = mapped_column(String(64), default="relatedto")
    display: Mapped[Optional[str]] = mapped_column(String(512))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    user_sub: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512))
    method: Mapped[str] = mapped_column(String(16))
    status_code: Mapped[int] = mapped_column(Integer)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
