from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import settings
from app.schemas import ExtractedRow
from app.services.excel import write_excel
from app.services.layout_extractor import extract_layout_fields
from app.services.ocr import ocr_service
from app.services.parser import error_row, parse_structured_text
from app.services.preprocess import preprocess_image
from app.services.storage import sha256_file, store


def _process_single_file(image_path: Path, confidence_threshold: float) -> tuple[ExtractedRow, str]:
    checksum = sha256_file(image_path)
    cached = store.get_cached_result(checksum)
    if cached:
        cached.image_name = image_path.name
        return cached, checksum

    row = extract_layout_fields(image_path)
    critical_fields = ["total_price", "target_price", "order_quantity", "yarn_requirement_total"]
    needs_fallback = (
        row.ocr_confidence < confidence_threshold
        or any(getattr(row, field_name, None) in (None, "", []) for field_name in critical_fields)
    )
    if needs_fallback:
        processed = preprocess_image(image_path)
        ocr = ocr_service.extract_text(processed, image_path, confidence_threshold)
        fallback_row = parse_structured_text(
            image_path.name,
            str(ocr["text"]),
            float(ocr["confidence"]),
            str(ocr["engine"]),
        )
        prefer_fallback_fields = {
            "total_price",
            "target_price",
            "order_quantity",
            "yarn_requirement_warp1",
            "yarn_requirement_weft1",
            "yarn_requirement_total",
            "fabric_weight_glm_inc_sizing",
        }
        for field_name in fallback_row.model_dump():
            fallback_value = getattr(fallback_row, field_name, None)
            current_value = getattr(row, field_name, None)
            if field_name in prefer_fallback_fields and fallback_value not in (None, "", []):
                setattr(row, field_name, fallback_value)
                continue
            if current_value in (None, "", []):
                setattr(row, field_name, fallback_value)
        row.ocr_engine = f"{row.ocr_engine}+{fallback_row.ocr_engine}"
        row.ocr_confidence = max(row.ocr_confidence, fallback_row.ocr_confidence)
        row.low_confidence_fields = [
            field_name
            for field_name in row.low_confidence_fields
            if not getattr(row, field_name, None)
        ]

    if row.low_confidence_fields and row.ocr_confidence < confidence_threshold:
        row.status = "REVIEW"
    elif not row.low_confidence_fields:
        row.status = "SUCCESS"
    store.set_cached_result(checksum, row)
    return row, checksum


async def run_job(
    job_id: str,
    upload_id: str,
    files: list[Path],
    batch_size: int,
    confidence_threshold: float,
    output_dir: Path,
    output_filename: str | None = None,
) -> None:
    output_path = output_dir / (output_filename or f"{job_id}.xlsx")
    store.update_job(
        job_id,
        status="running",
        message="Initializing OCR workers.",
        output_filename=output_path.name,
    )
    store.append_log(job_id, f"Starting job for upload {upload_id} with {len(files)} image(s).")

    executor = ThreadPoolExecutor(max_workers=settings.max_workers)
    loop = asyncio.get_running_loop()
    results: list[ExtractedRow] = []

    try:
        for index in range(0, len(files), batch_size):
            while True:
                current_job = store.get_job(job_id)
                if current_job is None:
                    raise RuntimeError("Job state disappeared.")
                if current_job.status == "stopped":
                    write_excel(results, output_path)
                    store.finalize_job(
                        job_id,
                        status="stopped",
                        message="Processing stopped. Partial Excel file is ready to download.",
                        output_filename=output_path.name,
                    )
                    store.append_log(job_id, "Job stopped by user.")
                    return
                if current_job.status == "paused":
                    write_excel(results, output_path)
                    store.update_job(
                        job_id,
                        message="Processing paused. Partial Excel file is ready to download.",
                        output_filename=output_path.name,
                    )
                    await asyncio.sleep(1)
                    continue
                break

            batch = files[index:index + batch_size]
            store.update_job(job_id, message=f"Processing batch {index // batch_size + 1}.")
            store.append_log(job_id, f"Processing batch of {len(batch)} file(s).")

            tasks = [
                loop.run_in_executor(executor, _process_single_file, image_path, confidence_threshold)
                for image_path in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for item, image_path in zip(batch_results, batch):
                if isinstance(item, Exception):
                    row = error_row(image_path, str(item))
                    store.append_log(job_id, f"{image_path.name} failed: {item}")
                else:
                    row, _checksum = item
                    store.append_log(
                        job_id,
                        f"{image_path.name} processed with {row.ocr_engine} at {row.ocr_confidence:.2f} confidence.",
                    )
                results.append(row)
                store.append_result(job_id, row)

            write_excel(results, output_path)
            store.update_job(job_id, output_filename=output_path.name)

        write_excel(results, output_path)
        store.finalize_job(
            job_id,
            status="completed",
            message="OCR processing completed. Excel file is ready to download.",
            output_filename=output_path.name,
        )
        store.append_log(job_id, f"Excel exported to {output_path.name}.")
    except Exception as exc:
        store.finalize_job(job_id, status="failed", message=f"Job failed: {exc}")
        store.append_log(job_id, f"Fatal job error: {exc}")
    finally:
        executor.shutdown(wait=False, cancel_futures=False)
