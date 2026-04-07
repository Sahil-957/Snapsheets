"use client";

import { Dropzone } from "@/components/dropzone";
import { ExportHistory } from "@/components/export-history";
import { PreviewTable } from "@/components/preview-table";
import { StatusPanel } from "@/components/status-panel";
import { fetchExports, fetchJobStatus, getDownloadUrl, pauseJob, startProcessing, stopJob, uploadImages } from "@/lib/api";
import { ExportEntry, JobStatus } from "@/types";
import { Download, LoaderCircle, Pause, Play, RefreshCw, Square, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [exports, setExports] = useState<ExportEntry[]>([]);
  const [uploadState, setUploadState] = useState("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingState, setProcessingState] = useState("idle");
  const [jobActionState, setJobActionState] = useState<"idle" | "pausing" | "stopping">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadExports = async () => {
      try {
        const items = await fetchExports();
        setExports(items);
      } catch {
        // Leave history empty if the backend is not ready yet.
      }
    };
    loadExports();
  }, []);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let interval: NodeJS.Timeout | null = null;
    let cancelled = false;

    const poll = async () => {
      try {
        const status = await fetchJobStatus(jobId);
        if (cancelled) {
          return;
        }
        setJob(status);
        setProcessingState(status.status);
        if (status.status === "completed" || status.status === "failed" || status.status === "stopped") {
          if (interval) {
            clearInterval(interval);
          }
        }
        const items = await fetchExports();
        if (!cancelled) {
          setExports(items);
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Unable to fetch job status.");
        }
      }
    };

    poll();
    interval = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [jobId]);

  const canProcess = useMemo(() => files.length > 0 && uploadState !== "uploading", [files.length, uploadState]);

  async function handleUpload() {
    if (files.length === 0) {
      return;
    }

    setError(null);
    setUploadState("uploading");
    setUploadProgress(0);
    setProcessingState("idle");
    setJob(null);
    setJobId(null);

    try {
      const response = await uploadImages(files, setUploadProgress);
      setUploadId(response.upload_id);
      setUploadProgress(100);
      setUploadState("uploaded");
    } catch (uploadError) {
      setUploadState("failed");
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    }
  }

  async function handleProcess() {
    if (!uploadId) {
      setError("Upload images before starting OCR processing.");
      return;
    }

    setError(null);
    setProcessingState("starting");

    try {
      const response = await startProcessing(uploadId);
      setJobId(response.job_id);
      setProcessingState(response.status);
    } catch (processError) {
      setProcessingState("failed");
      setError(processError instanceof Error ? processError.message : "Processing failed.");
    }
  }

  return (
    <main className="min-h-screen px-4 py-8 md:px-8">
      <div className="grid-bg mx-auto max-w-7xl rounded-[2.5rem] border border-white/70 bg-white/40 p-6 backdrop-blur md:p-10">
        <section className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-teal">Bulk OCR Workflow</p>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-tight md:text-6xl">
              Upload structured screenshots, parse them into rows, and export a ready-to-share Excel sheet.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-ink/70 md:text-lg">
              This app batches large image sets, preprocesses screenshots, runs hybrid OCR with a Google Vision fallback,
              and keeps processing even when some files fail.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleUpload}
                disabled={!canProcess}
                className="inline-flex items-center gap-2 rounded-full bg-coral px-5 py-3 text-sm font-semibold text-white transition hover:bg-coral/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {uploadState === "uploading" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Upload Images
              </button>
              <button
                type="button"
                onClick={handleProcess}
                disabled={!uploadId || processingState === "running" || processingState === "starting"}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {processingState === "running" || processingState === "starting" ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {processingState === "paused" ? "Resume Processing" : "Process Images"}
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!jobId) return;
                  setJobActionState("pausing");
                  setError(null);
                  try {
                    await pauseJob(jobId);
                    const status = await fetchJobStatus(jobId);
                    setJob(status);
                    setProcessingState(status.status);
                    setExports(await fetchExports());
                  } catch (pauseError) {
                    setError(pauseError instanceof Error ? pauseError.message : "Pause failed.");
                  } finally {
                    setJobActionState("idle");
                  }
                }}
                disabled={!jobId || processingState !== "running" || jobActionState !== "idle"}
                className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
              >
                {jobActionState === "pausing" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Pause className="h-4 w-4" />}
                Pause
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!jobId) return;
                  setJobActionState("stopping");
                  setError(null);
                  try {
                    await stopJob(jobId);
                    const status = await fetchJobStatus(jobId);
                    setJob(status);
                    setProcessingState(status.status);
                    setExports(await fetchExports());
                  } catch (stopError) {
                    setError(stopError instanceof Error ? stopError.message : "Stop failed.");
                  } finally {
                    setJobActionState("idle");
                  }
                }}
                disabled={!jobId || !["running", "paused", "pending"].includes(processingState) || jobActionState !== "idle"}
                className="inline-flex items-center gap-2 rounded-full border border-coral/20 bg-white px-5 py-3 text-sm font-semibold text-coral transition hover:bg-coral/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {jobActionState === "stopping" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                Stop
              </button>
              <a
                href={jobId && job?.output_filename ? getDownloadUrl(jobId) : "#"}
                className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-mist disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                Download Excel
              </a>
              <button
                type="button"
                onClick={() => {
                  setFiles([]);
                  setUploadId(null);
                  setJobId(null);
                  setJob(null);
                  setUploadState("idle");
                  setUploadProgress(0);
                  setProcessingState("idle");
                  setError(null);
                }}
                className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-mist"
              >
                <RefreshCw className="h-4 w-4" />
                Reset
              </button>
            </div>

            {error ? <p className="mt-4 text-sm text-coral">{error}</p> : null}
          </div>

          <Dropzone files={files} onFilesSelected={setFiles} disabled={uploadState === "uploading"} />
        </section>

        <section className="mt-8 grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <StatusPanel
            uploadState={uploadState}
            uploadProgress={uploadProgress}
            processingState={processingState}
            job={job}
          />
          <PreviewTable rows={job?.results ?? []} />
        </section>

        <section className="mt-8">
          <ExportHistory exports={exports} />
        </section>
      </div>
    </main>
  );
}
