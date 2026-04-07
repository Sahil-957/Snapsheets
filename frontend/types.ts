export type UploadResponse = {
  upload_id: string;
  file_count: number;
  files: { filename: string; checksum: string; size: number }[];
};

export type ProcessResponse = {
  job_id: string;
  upload_id: string;
  status: string;
};

export type ExtractedRow = {
  image_name: string;
  date: string | null;
  agent: string | null;
  customer: string | null;
  quality: string | null;
  warp_counts: string | null;
  weft_counts: string | null;
  total_price: string | null;
  target_price: string | null;
  order_quantity: string | null;
  yarn_requirement: string | null;
  composition: string | null;
  gsm_fabric_weight: string | null;
  ocr_engine: string;
  ocr_confidence: number;
  status: string;
  error_message: string | null;
  low_confidence_fields?: string[];
};

export type JobStatus = {
  job_id: string;
  upload_id: string;
  status: "pending" | "running" | "paused" | "stopped" | "completed" | "failed";
  total_files: number;
  processed_files: number;
  progress: number;
  message: string;
  output_filename: string | null;
  started_at: string | null;
  completed_at: string | null;
  logs: string[];
  results: ExtractedRow[];
  failed_images: string[];
};

export type JobActionResponse = {
  job_id: string;
  status: string;
  message: string;
};

export type ExportEntry = {
  job_id: string | null;
  filename: string;
  status: string;
  created_at: string;
  processed_files: number;
  total_files: number;
  download_url: string;
};
