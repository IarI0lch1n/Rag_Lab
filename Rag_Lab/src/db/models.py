from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mssql import NVARCHAR, VARBINARY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        NVARCHAR(255),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    uri: Mapped[str | None] = mapped_column(
        NVARCHAR(2048),
        nullable=True,
    )

    original_filename: Mapped[str | None] = mapped_column(
        NVARCHAR(512),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    file_extension: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    file_data: Mapped[bytes | None] = mapped_column(
        VARBINARY(None),
        nullable=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    last_error: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    etag: Mapped[str | None] = mapped_column(
        NVARCHAR(512),
        nullable=True,
    )

    last_modified: Mapped[str | None] = mapped_column(
        NVARCHAR(255),
        nullable=True,
    )

    git_branch: Mapped[str | None] = mapped_column(
        NVARCHAR(255),
        nullable=True,
    )

    git_commit_sha: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
        onupdate=func.sysdatetimeoffset(),
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_sources_source_type", "source_type"),
        Index("ix_sources_status", "status"),
        Index("ix_sources_content_hash", "content_hash"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "sources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        NVARCHAR(512),
        nullable=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        NVARCHAR(2048),
        nullable=True,
    )

    document_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    raw_text: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
        onupdate=func.sysdatetimeoffset(),
    )

    source: Mapped["Source"] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_documents_source_id", "source_id"),
        Index("ix_documents_content_hash", "content_hash"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        NVARCHAR(None),
        nullable=False,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    char_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    qdrant_point_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    document: Mapped["Document"] = relationship(
        back_populates="chunks",
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_chunks_document_chunk_index",
        ),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_content_hash", "content_hash"),
        Index("ix_chunks_qdrant_point_id", "qdrant_point_id"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "sources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="running",
        server_default="running",
    )

    run_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="sync",
        server_default="sync",
    )

    documents_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    documents_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    documents_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    documents_skipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    chunks_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source: Mapped["Source"] = relationship(
        back_populates="ingestion_runs",
    )

    __table_args__ = (
        Index("ix_ingestion_runs_source_id", "source_id"),
        Index("ix_ingestion_runs_status", "status"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str | None] = mapped_column(
        NVARCHAR(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
        onupdate=func.sysdatetimeoffset(),
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "chat_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        NVARCHAR(None),
        nullable=False,
    )

    citations_json: Mapped[str | None] = mapped_column(
        NVARCHAR(None),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
    )

    session: Mapped["ChatSession"] = relationship(
        back_populates="messages",
    )

    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
        Index("ix_chat_messages_created_at", "created_at"),
    )