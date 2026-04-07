"use client";

import clsx from "clsx";
import { FolderOpen, ImagePlus, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

type DropzoneProps = {
  files: File[];
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
};

type DataTransferItemWithEntry = DataTransferItem & {
  webkitGetAsEntry?: () => FileSystemEntry | null;
};

const acceptedFormats = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"];
const acceptedExtensions = new Set(acceptedFormats.map((format) => format.replace(".", "").toLowerCase()));

export function Dropzone({ files, onFilesSelected, disabled }: DropzoneProps) {
  const imagesInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function isAcceptedImage(file: File) {
    const extension = file.name.split(".").pop()?.toLowerCase();
    return Boolean(extension && acceptedExtensions.has(extension));
  }

  function mergeFiles(nextFiles: File[]) {
    if (nextFiles.length === 0) {
      return;
    }

    const unique = new Map<string, File>();
    [...files, ...nextFiles.filter(isAcceptedImage)].forEach((file) => {
      unique.set(`${file.name}-${file.size}-${file.lastModified}`, file);
    });
    onFilesSelected(Array.from(unique.values()));
  }

  function mergeFileList(list: FileList | null) {
    if (!list) {
      return;
    }
    mergeFiles(Array.from(list));
  }

  async function readFileEntry(entry: FileSystemFileEntry) {
    return await new Promise<File | null>((resolve) => {
      entry.file(
        (file) => resolve(file),
        () => resolve(null)
      );
    });
  }

  async function readDirectoryEntries(directory: FileSystemDirectoryEntry) {
    const reader = directory.createReader();
    const entries: FileSystemEntry[] = [];

    while (true) {
      const batch = await new Promise<FileSystemEntry[]>((resolve) => {
        reader.readEntries((items) => resolve(items), () => resolve([]));
      });

      if (batch.length === 0) {
        break;
      }

      entries.push(...batch);
    }

    return entries;
  }

  async function collectDroppedFiles(entries: FileSystemEntry[]) {
    const collected: File[] = [];

    for (const entry of entries) {
      if (entry.isFile) {
        const file = await readFileEntry(entry as FileSystemFileEntry);
        if (file && isAcceptedImage(file)) {
          collected.push(file);
        }
        continue;
      }

      if (entry.isDirectory) {
        const nestedEntries = await readDirectoryEntries(entry as FileSystemDirectoryEntry);
        collected.push(...(await collectDroppedFiles(nestedEntries)));
      }
    }

    return collected;
  }

  async function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);

    if (disabled) {
      return;
    }

    const items = Array.from(event.dataTransfer.items ?? []);
    const entries = items
      .map((item) => (item as DataTransferItemWithEntry).webkitGetAsEntry?.() ?? null)
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

    if (entries.length > 0) {
      mergeFiles(await collectDroppedFiles(entries));
      return;
    }

    mergeFileList(event.dataTransfer.files);
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
      onDrop={handleDrop}
    >
      <input
        ref={imagesInputRef}
        type="file"
        accept={acceptedFormats.join(",")}
        multiple
        className="hidden"
        disabled={disabled}
        onChange={(event) => mergeFileList(event.target.files)}
      />
      <input
        ref={folderInputRef}
        type="file"
        accept={acceptedFormats.join(",")}
        multiple
        className="hidden"
        disabled={disabled}
        onChange={(event) => mergeFileList(event.target.files)}
        {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
      />

      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-full bg-ink p-4 text-white">
          <UploadCloud className="h-8 w-8" />
        </div>
        <div>
          <p className="text-xl font-semibold">Drop structured form screenshots here</p>
          <p className="mt-2 text-sm text-ink/65">
            Optimized for large batches. Drag images or folders here, or pick individual screenshots and full folders.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            disabled={disabled}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed"
            onClick={() => imagesInputRef.current?.click()}
          >
            <ImagePlus className="h-4 w-4" />
            Choose Images
          </button>
          <button
            type="button"
            disabled={disabled}
            className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-mist disabled:cursor-not-allowed"
            onClick={() => folderInputRef.current?.click()}
          >
            <FolderOpen className="h-4 w-4" />
            Choose Folder
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-2xl bg-mist px-4 py-3 text-sm text-ink/75">
        {files.length === 0 ? "No images selected yet." : `${files.length} image(s) queued for upload.`}
      </div>
    </div>
  );
}
