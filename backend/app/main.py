from __future__ import annotations

from datetime import datetime, timedelta
import re

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile

from app.config import settings
from app.schemas import ExportEntry, JobActionResponse, JobStatus, ProcessRequest, ProcessResponse, UploadResponse, UploadedFileMeta
from app.services.pipeline import run_job
from app.services.storage import sha256_file, store

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_storage() -> None:
    for path in [settings.storage_root, settings.uploads_path, settings.outputs_path, settings.temp_path]:
        path.mkdir(parents=True, exist_ok=True)


ensure_storage()


def purge_expired_exports() -> None:
    cutoff = datetime.now() - timedelta(days=settings.export_retention_days)
    for file_path in settings.outputs_path.glob("*.xlsx"):
        modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        if modified_at < cutoff:
            file_path.unlink(missing_ok=True)


def build_export_filename(name: str | None, fallback_job_id: str) -> str:
    if name:
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "", name).strip()
        safe = safe.rstrip(". ")
        if safe:
            if not safe.lower().endswith(".xlsx"):
                safe = f"{safe}.xlsx"
            return safe
    return f"{fallback_job_id}.xlsx"


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health")
def health() -> dict[str, str]:
    purge_expired_exports()
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_images(request: Request) -> UploadResponse:
    form = await request.form(
        max_files=settings.upload_max_files,
        max_part_size=settings.upload_max_part_size_mb * 1024 * 1024,
    )
    files = [value for _, value in form.multi_items() if isinstance(value, UploadFile)]
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    upload_id = store.create_upload([])
    upload_dir = settings.uploads_path / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    metadata = []

    for file in files:
        safe_name = file.filename.split("\\")[-1].split("/")[-1]
        target_path = upload_dir / safe_name
        content = await file.read()
        target_path.write_bytes(content)
        checksum = sha256_file(target_path)
        uploaded_files.append(target_path)
        metadata.append(
            UploadedFileMeta(filename=safe_name, checksum=checksum, size=len(content))
        )

    store.set_upload_files(upload_id, uploaded_files)

    return UploadResponse(upload_id=upload_id, file_count=len(uploaded_files), files=metadata)


@app.post("/process", response_model=ProcessResponse)
async def process_images(request: ProcessRequest, background_tasks: BackgroundTasks) -> ProcessResponse:
    purge_expired_exports()
    files = store.get_upload_files(request.upload_id)
    if not files:
        raise HTTPException(status_code=404, detail="Upload session not found or empty.")

    for existing_job in store.list_jobs():
        if existing_job.upload_id == request.upload_id and existing_job.status == "paused":
            resumed = store.resume_job(existing_job.job_id)
            store.append_log(existing_job.job_id, "Job resumed by user.")
            return ProcessResponse(job_id=resumed.job_id, upload_id=request.upload_id, status=resumed.status)

    job = store.create_job(request.upload_id, len(files))
    batch_size = request.batch_size or settings.batch_size
    confidence_threshold = request.confidence_threshold or settings.tesseract_confidence_threshold
    output_filename = build_export_filename(request.export_name, job.job_id)
    store.update_job(job.job_id, output_filename=output_filename)

    background_tasks.add_task(
        run_job,
        job.job_id,
        request.upload_id,
        files,
        batch_size,
        confidence_threshold,
        settings.outputs_path,
        output_filename,
    )
    return ProcessResponse(job_id=job.job_id, upload_id=request.upload_id, status=job.status)


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.post("/jobs/{job_id}/pause", response_model=JobActionResponse)
async def pause_job(job_id: str) -> JobActionResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    updated = store.pause_job(job_id)
    store.append_log(job_id, "Pause requested by user.")
    return JobActionResponse(job_id=job_id, status=updated.status, message=updated.message)


@app.post("/jobs/{job_id}/stop", response_model=JobActionResponse)
async def stop_job(job_id: str) -> JobActionResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    updated = store.stop_job(job_id)
    store.append_log(job_id, "Stop requested by user.")
    return JobActionResponse(job_id=job_id, status=updated.status, message=updated.message)


@app.get("/exports", response_model=list[ExportEntry])
async def list_exports() -> list[ExportEntry]:
    purge_expired_exports()
    jobs_by_filename = {
        job.output_filename: job
        for job in store.list_jobs()
        if job.output_filename
    }
    exports: list[ExportEntry] = []
    for file_path in sorted(settings.outputs_path.glob("*.xlsx"), key=lambda item: item.stat().st_mtime, reverse=True):
        job = jobs_by_filename.get(file_path.name)
        exports.append(
            ExportEntry(
                job_id=job.job_id if job else None,
                filename=file_path.name,
                status=job.status if job else "completed",
                created_at=datetime.fromtimestamp(file_path.stat().st_mtime),
                processed_files=job.processed_files if job else 0,
                total_files=job.total_files if job else 0,
                download_url=f"/download?job_id={job.job_id}" if job else f"/exports/{file_path.name}",
            )
        )
    return exports


@app.get("/exports/{filename}")
async def download_previous_export(filename: str) -> FileResponse:
    purge_expired_exports()
    file_path = settings.outputs_path / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.delete("/exports/{filename}", response_model=JobActionResponse)
async def delete_previous_export(filename: str) -> JobActionResponse:
    file_path = settings.outputs_path / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    file_path.unlink(missing_ok=True)
    return JobActionResponse(job_id=filename, status="deleted", message=f"{filename} deleted successfully.")


@app.get("/download")
async def download_excel(job_id: str) -> FileResponse:
    purge_expired_exports()
    job = store.get_job(job_id)
    if not job or not job.output_filename:
        raise HTTPException(status_code=404, detail="Excel file not ready.")

    file_path = settings.outputs_path / job.output_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Excel file missing on disk.")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"output-{job_id}.xlsx",
    )
