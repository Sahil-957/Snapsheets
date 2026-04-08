from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
from google.cloud import vision

from app.config import settings


class OCRService:
    def __init__(self) -> None:
        self._vision_client: vision.ImageAnnotatorClient | None = None
        self._tessdata_dir: Path | None = None
        self._tesseract_available = False
        self._vision_credentials_path: Path | None = None
        tesseract_cmd = settings.tesseract_cmd or self._detect_tesseract_cmd()
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self._tesseract_available = Path(tesseract_cmd).exists()
            tessdata_dir = Path(tesseract_cmd).parent / "tessdata"
            if tessdata_dir.exists():
                self._tessdata_dir = tessdata_dir
                os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        self._configure_google_credentials()

    def _detect_tesseract_cmd(self) -> str | None:
        candidates = [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def extract_text(self, image: np.ndarray, original_path: Path, threshold: float) -> dict[str, Any]:
        tesseract_result = self._run_tesseract(image)
        if tesseract_result["confidence"] >= threshold or not self._vision_ready():
            return tesseract_result

        vision_result = self._run_google_vision(original_path)
        return vision_result if vision_result["text"] else tesseract_result

    def _run_tesseract(self, image: np.ndarray) -> dict[str, Any]:
        if not self._tesseract_available:
            return {
                "text": "",
                "confidence": 0.0,
                "engine": "tesseract-unavailable",
                "words": [],
            }

        config = "--oem 3 --psm 6"
        try:
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
        except (pytesseract.TesseractNotFoundError, RuntimeError, OSError):
            self._tesseract_available = False
            return {
                "text": "",
                "confidence": 0.0,
                "engine": "tesseract-unavailable",
                "words": [],
            }

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
            "words": [],
        }

    def _vision_ready(self) -> bool:
        configured_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if configured_path and Path(configured_path).exists():
            return True
        return self._vision_credentials_path is not None

    def _get_vision_client(self) -> vision.ImageAnnotatorClient:
        if self._vision_client is None:
            self._vision_client = vision.ImageAnnotatorClient()
        return self._vision_client

    def _run_google_vision(self, image_path: Path) -> dict[str, Any]:
        try:
            client = self._get_vision_client()
            content = image_path.read_bytes()
            response = client.document_text_detection(image=vision.Image(content=content))
            if response.error.message:
                raise RuntimeError(response.error.message)
        except Exception:
            return {
                "text": "",
                "confidence": 0.0,
                "engine": "google-vision-unavailable",
                "words": [],
            }

        annotation = response.full_text_annotation
        text = annotation.text if annotation else ""
        scores = [page.confidence for page in annotation.pages] if annotation and annotation.pages else []
        confidence = round((sum(scores) / len(scores)) * 100, 2) if scores else 0.0
        words = self._extract_google_words(annotation)
        return {
            "text": text,
            "confidence": confidence,
            "engine": "google-vision",
            "words": words,
        }

    def extract_crop_text(
        self,
        image: np.ndarray,
        *,
        config: str = "--psm 6",
        scale: int = 4,
        threshold: bool = False,
    ) -> tuple[str, float]:
        if not self._tesseract_available:
            return "", 0.0

        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(grayscale, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if threshold:
            enlarged = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        try:
            data = pytesseract.image_to_data(
                enlarged,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
        except (pytesseract.TesseractNotFoundError, RuntimeError, OSError):
            self._tesseract_available = False
            return "", 0.0

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

    def _configure_google_credentials(self) -> None:
        credentials_json = settings.google_application_credentials_json
        credentials_path = settings.google_application_credentials

        if credentials_json:
            try:
                temp_dir = settings.temp_path
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / "google-vision-service-account.json"
                payload = json.loads(credentials_json)
                temp_path.write_text(json.dumps(payload), encoding="utf-8")
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(temp_path)
                self._vision_credentials_path = temp_path
                return
            except (OSError, json.JSONDecodeError, TypeError):
                self._vision_credentials_path = None

        if credentials_path:
            path = Path(credentials_path)
            if path.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
                self._vision_credentials_path = path

    def _extract_google_words(self, annotation: vision.TextAnnotation | None) -> list[dict[str, float | str]]:
        if not annotation:
            return []

        words: list[dict[str, float | str]] = []
        for page in annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        token = "".join(symbol.text for symbol in word.symbols).strip()
                        if not token:
                            continue
                        vertices = word.bounding_box.vertices
                        xs = [vertex.x for vertex in vertices if vertex.x is not None]
                        ys = [vertex.y for vertex in vertices if vertex.y is not None]
                        if not xs or not ys:
                            continue
                        left = float(min(xs))
                        right = float(max(xs))
                        top = float(min(ys))
                        bottom = float(max(ys))
                        words.append(
                            {
                                "text": token,
                                "left": left,
                                "right": right,
                                "top": top,
                                "bottom": bottom,
                                "cx": (left + right) / 2.0,
                                "cy": (top + bottom) / 2.0,
                            }
                        )
        return words



ocr_service = OCRService()
