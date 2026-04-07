from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from google.cloud import vision

from app.config import settings


class OCRService:
    def __init__(self) -> None:
        self._vision_client: vision.ImageAnnotatorClient | None = None
        self._tessdata_dir: Path | None = None
        tesseract_cmd = settings.tesseract_cmd or self._detect_tesseract_cmd()
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            tessdata_dir = Path(tesseract_cmd).parent / "tessdata"
            if tessdata_dir.exists():
                self._tessdata_dir = tessdata_dir
                os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

    def _detect_tesseract_cmd(self) -> str | None:
        candidates = [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def extract_text(self, image: np.ndarray, original_path: Path, threshold: float) -> dict[str, str | float]:
        tesseract_result = self._run_tesseract(image)
        if tesseract_result["confidence"] >= threshold or not self._vision_ready():
            return tesseract_result

        vision_result = self._run_google_vision(original_path)
        return vision_result if vision_result["text"] else tesseract_result

    def _run_tesseract(self, image: np.ndarray) -> dict[str, str | float]:
        config = "--oem 3 --psm 6"
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            config=config,
        )

        tokens: list[str] = []
        confidences: list[float] = []
        for index, token in enumerate(data.get("text", [])):
            value = token.strip()
            if not value:
                continue
            tokens.append(value)
            try:
                confidence = float(data["conf"][index])
            except (ValueError, KeyError):
                confidence = -1
            if confidence >= 0:
                confidences.append(confidence)

        return {
            "text": "\n".join(tokens),
            "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "engine": "tesseract",
        }

    def _vision_ready(self) -> bool:
        return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or settings.google_application_credentials)

    def _get_vision_client(self) -> vision.ImageAnnotatorClient:
        if self._vision_client is None:
            self._vision_client = vision.ImageAnnotatorClient()
        return self._vision_client

    def _run_google_vision(self, image_path: Path) -> dict[str, str | float]:
        client = self._get_vision_client()
        content = image_path.read_bytes()
        response = client.document_text_detection(image=vision.Image(content=content))
        if response.error.message:
            raise RuntimeError(response.error.message)

        annotation = response.full_text_annotation
        text = annotation.text if annotation else ""
        scores = [page.confidence for page in annotation.pages] if annotation and annotation.pages else []
        confidence = round((sum(scores) / len(scores)) * 100, 2) if scores else 0.0
        return {
            "text": text,
            "confidence": confidence,
            "engine": "google-vision",
        }

    def extract_crop_text(
        self,
        image: np.ndarray,
        *,
        config: str = "--psm 6",
        scale: int = 4,
        threshold: bool = False,
    ) -> tuple[str, float]:
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(grayscale, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if threshold:
            enlarged = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        data = pytesseract.image_to_data(
            enlarged,
            output_type=pytesseract.Output.DICT,
            config=config,
        )

        tokens: list[str] = []
        confidences: list[float] = []
        for index, token in enumerate(data.get("text", [])):
            value = token.strip()
            if not value:
                continue
            tokens.append(value)
            try:
                confidence = float(data["conf"][index])
            except (ValueError, KeyError):
                confidence = -1
            if confidence >= 0:
                confidences.append(confidence)

        text = " ".join(tokens).strip()
        confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        return text, confidence



ocr_service = OCRService()
