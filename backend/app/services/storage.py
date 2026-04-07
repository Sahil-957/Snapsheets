from __future__ import annotations

import hashlib
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.schemas import ExtractedRow, JobStatus


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobStatus] = {}
        self._uploads: dict[str, list[Path]] = {}
        self._cache: dict[str, ExtractedRow] = {}

    def create_upload(self, files: list[Path]) -> str:
        upload_id = uuid4().hex
        with self._lock:
            self._uploads[upload_id] = files
        return upload_id

    def set_upload_files(self, upload_id: str, files: list[Path]) -> None:
        with self._lock:
            self._uploads[upload_id] = files

    def get_upload_files(self, upload_id: str) -> list[Path]:
        with self._lock:
            return list(self._uploads.get(upload_id, []))

    def create_job(self, upload_id: str, total_files: int) -> JobStatus:
        job = JobStatus(
            job_id=uuid4().hex,
            upload_id=upload_id,
            total_files=total_files,
            status="pending",
            message="Queued for OCR processing.",
            started_at=datetime.utcnow(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> JobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def list_jobs(self) -> list[JobStatus]:
        with self._lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def update_job(self, job_id: str, **kwargs) -> JobStatus:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job, key, value)
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.logs.append(f"[{datetime.utcnow().isoformat(timespec='seconds')}] {message}")
            job.logs = job.logs[-200:]
            self._jobs[job_id] = job

    def append_result(self, job_id: str, row: ExtractedRow) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.results.append(row)
            job.processed_files += 1
            if row.status == "ERROR":
                job.failed_images.append(row.image_name)
            job.progress = round((job.processed_files / max(job.total_files, 1)) * 100, 2)
            self._jobs[job_id] = job

    def pause_job(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs[job_id]
            if job.status == "running":
                job.status = "paused"
                job.message = "Pause requested. Waiting for current batch to finish."
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def resume_job(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs[job_id]
            if job.status == "paused":
                job.status = "running"
                job.message = "Job resumed."
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def stop_job(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs[job_id]
            if job.status in {"running", "paused", "pending"}:
                job.status = "stopped"
                job.message = "Stop requested. Finishing current batch before stopping."
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def finalize_job(self, job_id: str, *, status: str, message: str, output_filename: str | None = None) -> JobStatus:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.message = message
            job.output_filename = output_filename
            job.progress = 100.0 if status == "completed" else job.progress
            job.completed_at = datetime.utcnow()
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def get_cached_result(self, checksum: str) -> ExtractedRow | None:
        with self._lock:
            result = self._cache.get(checksum)
            return result.model_copy(deep=True) if result else None

    def set_cached_result(self, checksum: str, row: ExtractedRow) -> None:
        with self._lock:
            self._cache[checksum] = row.model_copy(deep=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


store = InMemoryStore()
