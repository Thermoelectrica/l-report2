"""Database models for render tracking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Render(Base):
    """Track render jobs and their status."""

    __tablename__ = "renders"

    # Use parameter hash as primary key for stable cache lookup
    parameter_hash = Column(
        String(64), primary_key=True, comment="SHA256 hash of report_id + parameters"
    )

    report_id = Column(
        String(255), nullable=False, index=True, comment="Report identifier"
    )
    parameters_json = Column(Text, nullable=False, comment="JSON-encoded parameters")

    status = Column(
        String(50),
        nullable=False,
        index=True,
        comment="PENDING, RUNNING, COMPLETED, FAILED",
    )

    # Output file information
    output_format = Column(
        String(50), nullable=False,
        comment="Output format (weasyprint, docx, etc.)"
    )
    file_extension = Column(
        String(10), nullable=False,
        comment="File extension (pdf, docx, etc.)"
    )
    output_path = Column(
        String(512), nullable=True,
        comment="Storage path to output file"
    )
    file_size_bytes = Column(Integer, nullable=True, comment="Output file size in bytes")

    error_message = Column(
        Text, nullable=True, comment="Error details if status is FAILED"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When render was requested",
    )
    started_at = Column(DateTime, nullable=True, comment="When rendering started")
    completed_at = Column(
        DateTime, nullable=True, index=True, comment="When rendering finished"
    )

    __table_args__ = (
        Index("ix_renders_report_status", "report_id", "status"),
        Index("ix_renders_completed_at_status", "completed_at", "status"),
    )

    def __repr__(self):
        return f"<Render(hash={self.parameter_hash[:8]}, report={self.report_id}, status={self.status})>"
