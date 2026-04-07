import { getExportDownloadUrl } from "@/lib/api";
import { ExportEntry } from "@/types";
import { Download, Trash2 } from "lucide-react";

type ExportHistoryProps = {
  exports: ExportEntry[];
  onDelete: (filename: string) => void | Promise<void>;
};

export function ExportHistory({ exports, onDelete }: ExportHistoryProps) {
  return (
    <section className="rounded-[2rem] bg-white/85 p-6 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Previous Exports</h2>
          <p className="mt-2 text-sm text-ink/65">
            Download completed, paused, or stopped Excel files from earlier runs.
          </p>
        </div>
        <div className="rounded-full bg-mist px-4 py-2 text-sm font-medium text-ink/70">
          {exports.length} file(s)
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {exports.length === 0 ? (
          <p className="text-sm text-ink/65">No exports yet. Process a batch to create your first workbook.</p>
        ) : (
          exports.map((entry) => (
            <div key={entry.filename} className="flex flex-col gap-3 rounded-2xl bg-mist/80 p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-semibold text-ink">{entry.filename}</p>
                <p className="mt-1 text-sm text-ink/65">
                  Status: {entry.status} • Files: {entry.processed_files}/{entry.total_files || entry.processed_files} • Created:{" "}
                  {new Date(entry.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <a
                  href={getExportDownloadUrl(entry)}
                  className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
                >
                  <Download className="h-4 w-4" />
                  Download
                </a>
                <button
                  type="button"
                  onClick={() => onDelete(entry.filename)}
                  className="inline-flex items-center gap-2 rounded-full border border-coral/20 bg-white px-4 py-2 text-sm font-semibold text-coral transition hover:bg-coral/5"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
