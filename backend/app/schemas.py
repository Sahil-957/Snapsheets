from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UploadedFileMeta(BaseModel):
    filename: str
    checksum: str
    size: int


class UploadResponse(BaseModel):
    upload_id: str
    file_count: int
    files: list[UploadedFileMeta]


class ProcessRequest(BaseModel):
    upload_id: str
    batch_size: int | None = Field(default=None, ge=1, le=100)
    confidence_threshold: float | None = Field(default=None, ge=0, le=100)


class ProcessResponse(BaseModel):
    job_id: str
    upload_id: str
    status: str


class JobActionResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExportEntry(BaseModel):
    job_id: str | None = None
    filename: str
    status: str
    created_at: datetime
    processed_files: int = 0
    total_files: int = 0
    download_url: str


class ExtractedRow(BaseModel):
    image_name: str
    date: str | None = None
    agent: str | None = None
    customer: str | None = None
    quality: str | None = None
    warp_counts: str | None = None
    weft_counts: str | None = None
    total_price: str | None = None
    target_price: str | None = None
    order_quantity: str | None = None
    yarn_requirement: str | None = None
    composition: str | None = None
    gsm_fabric_weight: str | None = None
    ocr_engine: str = "tesseract"
    ocr_confidence: float = 0.0
    status: str = "SUCCESS"
    error_message: str | None = None
    low_confidence_fields: list[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    upload_id: str
    status: Literal["pending", "running", "paused", "stopped", "completed", "failed"] = "pending"
    total_files: int = 0
    processed_files: int = 0
    progress: float = 0.0
    message: str = "Job created."
    output_filename: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    logs: list[str] = Field(default_factory=list)
    results: list[ExtractedRow] = Field(default_factory=list)
    failed_images: list[str] = Field(default_factory=list)
