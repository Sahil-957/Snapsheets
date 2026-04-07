import { ExportEntry, JobActionResponse, JobStatus, ProcessResponse, UploadResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function uploadImages(
  files: File[],
  onProgress?: (progress: number) => void
): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return new Promise<UploadResponse>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/upload`);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(JSON.parse(request.responseText) as UploadResponse);
      } else {
        reject(new Error(request.responseText || `Request failed with ${request.status}`));
      }
    };

    request.onerror = () => reject(new Error("Network error while uploading files."));
    request.send(formData);
  });
}

export async function startProcessing(uploadId: string): Promise<ProcessResponse> {
  const response = await fetch(`${API_BASE_URL}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId }),
  });

  return parseJson<ProcessResponse>(response);
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    cache: "no-store",
  });

  return parseJson<JobStatus>(response);
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/download?job_id=${jobId}`;
}

export function getExportDownloadUrl(entry: ExportEntry): string {
  if (entry.job_id) {
    return `${API_BASE_URL}/download?job_id=${entry.job_id}`;
  }
  return `${API_BASE_URL}/exports/${entry.filename}`;
}

export async function pauseJob(jobId: string): Promise<JobActionResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/pause`, { method: "POST" });
  return parseJson<JobActionResponse>(response);
}

export async function stopJob(jobId: string): Promise<JobActionResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/stop`, { method: "POST" });
  return parseJson<JobActionResponse>(response);
}

export async function fetchExports(): Promise<ExportEntry[]> {
  const response = await fetch(`${API_BASE_URL}/exports`, {
    cache: "no-store",
  });
  return parseJson<ExportEntry[]>(response);
}
