import { ExportEntry, JobActionResponse, JobStatus, ProcessResponse, UploadResponse } from "@/types";

function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    const { hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }
  }

  throw new Error("API base URL is not configured. Set NEXT_PUBLIC_API_BASE_URL to your deployed FastAPI URL.");
}

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
  const apiBaseUrl = resolveApiBaseUrl();
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return new Promise<UploadResponse>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiBaseUrl}/upload`);

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

    request.onerror = () =>
      reject(
        new Error(
          `Network error while uploading files. Check that the backend is reachable at ${apiBaseUrl} and allowed by CORS.`
        )
      );
    request.send(formData);
  });
}

export async function startProcessing(uploadId: string, exportName?: string): Promise<ProcessResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, export_name: exportName || null }),
  });

  return parseJson<ProcessResponse>(response);
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${resolveApiBaseUrl()}/jobs/${jobId}`, {
    cache: "no-store",
  });

  return parseJson<JobStatus>(response);
}

export function getDownloadUrl(jobId: string): string {
  return `${resolveApiBaseUrl()}/download?job_id=${jobId}`;
}

export function getExportDownloadUrl(entry: ExportEntry): string {
  const apiBaseUrl = resolveApiBaseUrl();
  if (entry.job_id) {
    return `${apiBaseUrl}/download?job_id=${entry.job_id}`;
  }
  return `${apiBaseUrl}/exports/${entry.filename}`;
}

export async function pauseJob(jobId: string): Promise<JobActionResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/jobs/${jobId}/pause`, { method: "POST" });
  return parseJson<JobActionResponse>(response);
}

export async function stopJob(jobId: string): Promise<JobActionResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/jobs/${jobId}/stop`, { method: "POST" });
  return parseJson<JobActionResponse>(response);
}

export async function fetchExports(): Promise<ExportEntry[]> {
  const response = await fetch(`${resolveApiBaseUrl()}/exports`, {
    cache: "no-store",
  });
  return parseJson<ExportEntry[]>(response);
}

export async function deleteExport(filename: string): Promise<JobActionResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}/exports/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  return parseJson<JobActionResponse>(response);
}
