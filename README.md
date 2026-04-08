# Bulk OCR Extractor

Production-oriented full-stack application for bulk OCR-based structured data extraction from screenshots of forms.

## What It Does

- Upload large batches of screenshots from the Next.js frontend
- Store upload sessions on the FastAPI backend
- Preprocess images with OpenCV before OCR
- Run Tesseract first to minimize cost
- Fallback to Google Vision only when confidence is below a threshold
- Parse structured fields using regex and keyword matching
- Export the extracted rows as an Excel workbook
- Continue processing even when individual images fail

## Project Structure

```text
ocrtp/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── main.py
│   │   └── schemas.py
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── .env.example
│   └── package.json
└── sample-data/
```

## Backend Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update:
   - `TESSERACT_CMD` if Tesseract is not on your PATH
   - `GOOGLE_APPLICATION_CREDENTIALS` with your Google Vision service account JSON path
   - or `GOOGLE_APPLICATION_CREDENTIALS_JSON` with the raw service account JSON for cloud deployments like Render
4. Start the API:

```bash
python run.py
```

API endpoints:

- `POST /upload`
- `POST /process`
- `GET /jobs/{job_id}`
- `GET /download?job_id=...`

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Copy `.env.example` to `.env.local`
3. Start the frontend:

```bash
npm run dev
```

Frontend default URL: `http://localhost:3000`

For Vercel deployments, set `NEXT_PUBLIC_API_BASE_URL` to your public FastAPI backend URL on Render, for example:

```text
NEXT_PUBLIC_API_BASE_URL=https://your-backend.onrender.com
```

## Workflow

1. Upload a batch of images.
2. Start processing.
3. The frontend polls job status and shows progress and logs.
4. Review extracted rows in the preview table.
5. Download the generated Excel workbook.

## Extraction Logic

The parser targets forms with consistent layout and looks for these fields:

- Date
- Agent
- Customer
- Quality
- Warp Count(s)
- Weft Count(s)
- Total Price
- Target Price
- Order Quantity
- Yarn Requirement
- Composition
- GSM / Fabric Weight

The current implementation uses:

- Layout-aware cropping
- Grayscale conversion
- Adaptive thresholding
- Regex and keyword matching
- Low-confidence field marking for review
- In-memory caching by file checksum to avoid reprocessing duplicates
- Automatic cleanup of old Excel exports after 7 days by default

## Notes for Production

- Move the in-memory store to Redis or a database for multi-instance deployments.
- Use a persistent task queue like Celery, Dramatiq, or RQ for long-running jobs.
- Mount `storage/` on persistent disk or object storage.
- Add authentication and request rate limiting before exposing publicly.
- Add structured logging and monitoring for OCR failure analysis.
