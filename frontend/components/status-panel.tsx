import { JobStatus } from "@/types";

type StatusPanelProps = {
  uploadState: string;
  uploadProgress: number;
  processingState: string;
  job: JobStatus | null;
};

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-ink/10">
      <div
        className="h-full rounded-full bg-teal transition-all duration-500"
        style={{ width: `${Math.max(4, value)}%` }}
      />
    </div>
  );
}

export function StatusPanel({ uploadState, uploadProgress, processingState, job }: StatusPanelProps) {
  return (
    <section className="rounded-[2rem] bg-white/85 p-6 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-ink/45">Run Status</p>
          <h2 className="mt-2 text-2xl font-semibold">Monitor OCR throughput</h2>
        </div>
        <div className="rounded-full border border-ink/10 px-4 py-2 text-sm text-ink/65">
          Upload: {uploadState}
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl bg-mist p-4">
          <p className="text-sm text-ink/55">Upload Progress</p>
          <p className="mt-2 text-lg font-semibold">{uploadProgress}%</p>
        </div>
        <div className="rounded-2xl bg-mist p-4">
          <p className="text-sm text-ink/55">Processing State</p>
          <p className="mt-2 text-lg font-semibold capitalize">{processingState}</p>
        </div>
        <div className="rounded-2xl bg-mist p-4">
          <p className="text-sm text-ink/55">Processed Files</p>
          <p className="mt-2 text-lg font-semibold">{job ? `${job.processed_files} / ${job.total_files}` : "0 / 0"}</p>
        </div>
      </div>

      <div className="mt-6">
        <ProgressBar value={job?.progress ?? 0} />
        <p className="mt-3 text-sm text-ink/65">{job?.message ?? "Waiting for uploads."}</p>
      </div>

      <div className="mt-4 rounded-2xl bg-mist p-4">
        <p className="text-sm text-ink/55">Failed Images</p>
        <p className="mt-2 text-lg font-semibold">{job?.failed_images.length ?? 0}</p>
      </div>

      <div className="mt-6 rounded-2xl border border-ink/10 bg-ink px-4 py-4 text-sm text-white">
        <p className="font-semibold">Job Logs</p>
        <div className="mt-3 max-h-52 space-y-2 overflow-auto text-white/80">
          {(job?.logs ?? ["Logs will appear here while OCR and parsing are running."]).map((log) => (
            <p key={log}>{log}</p>
          ))}
        </div>
      </div>
    </section>
  );
}
