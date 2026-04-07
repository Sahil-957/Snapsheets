"use client";

import clsx from "clsx";
import { ImagePlus, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

type DropzoneProps = {
  files: File[];
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
};

const acceptedFormats = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"];

export function Dropzone({ files, onFilesSelected, disabled }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function mergeFiles(list: FileList | null) {
    if (!list) {
      return;
    }

    const unique = new Map<string, File>();
    [...files, ...Array.from(list)].forEach((file) => {
      unique.set(`${file.name}-${file.size}-${file.lastModified}`, file);
    });
    onFilesSelected(Array.from(unique.values()));
  }

  return (
    <div
      className={clsx(
        "rounded-[2rem] border border-dashed border-ink/20 bg-white/80 p-8 shadow-panel transition",
        isDragging && "border-coral bg-coral/5",
        disabled && "cursor-not-allowed opacity-70"
      )}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) {
          setIsDragging(true);
        }
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        if (!disabled) {
          mergeFiles(event.dataTransfer.files);
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={acceptedFormats.join(",")}
        multiple
        className="hidden"
        disabled={disabled}
        onChange={(event) => mergeFiles(event.target.files)}
      />

      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-full bg-ink p-4 text-white">
          <UploadCloud className="h-8 w-8" />
        </div>
        <div>
          <p className="text-xl font-semibold">Drop structured form screenshots here</p>
          <p className="mt-2 text-sm text-ink/65">
            Optimized for large batches. Add 1000+ screenshots and process them in one run.
          </p>
        </div>
        <button
          type="button"
          disabled={disabled}
          className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed"
          onClick={() => inputRef.current?.click()}
        >
          <ImagePlus className="h-4 w-4" />
          Choose Images
        </button>
      </div>

      <div className="mt-6 rounded-2xl bg-mist px-4 py-3 text-sm text-ink/75">
        {files.length === 0 ? "No images selected yet." : `${files.length} image(s) queued for upload.`}
      </div>
    </div>
  );
}
