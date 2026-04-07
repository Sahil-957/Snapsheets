import { ExtractedRow } from "@/types";
import clsx from "clsx";

type PreviewTableProps = {
  rows: ExtractedRow[];
};

const columns: { key: keyof ExtractedRow; label: string }[] = [
  { key: "image_name", label: "Image" },
  { key: "date", label: "Date" },
  { key: "agent", label: "Agent" },
  { key: "customer", label: "Customer" },
  { key: "quality", label: "Quality" },
  { key: "warp_counts", label: "Warp Count(s)" },
  { key: "weft_counts", label: "Weft Count(s)" },
  { key: "total_price", label: "Total Price" },
  { key: "target_price", label: "Target Price" },
  { key: "order_quantity", label: "Order Quantity" },
  { key: "yarn_requirement", label: "Yarn Requirement" },
  { key: "composition", label: "Composition" },
  { key: "gsm_fabric_weight", label: "GSM / Weight" },
  { key: "ocr_confidence", label: "OCR Confidence" },
  { key: "status", label: "Status" }
];

export function PreviewTable({ rows }: PreviewTableProps) {
  if (rows.length === 0) {
    return (
      <section className="rounded-[2rem] bg-white/85 p-6 shadow-panel">
        <h2 className="text-2xl font-semibold">Preview</h2>
        <p className="mt-4 text-sm text-ink/65">
          Extracted rows will appear here after the job starts returning results.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-[2rem] bg-white/85 p-6 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Extracted Data Preview</h2>
          <p className="mt-2 text-sm text-ink/65">
            Low-confidence rows are highlighted so they can be reviewed before export.
          </p>
        </div>
        <div className="rounded-full bg-coral/10 px-4 py-2 text-sm font-medium text-coral">
          {rows.filter((row) => row.low_confidence_fields?.length).length} low-confidence row(s)
        </div>
      </div>

      <div className="mt-6 overflow-auto">
        <table className="min-w-full border-separate border-spacing-y-2 text-left text-sm">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} className="px-3 py-2 font-semibold text-ink/65">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.image_name}-${row.status}`}
                className={clsx("rounded-2xl bg-mist/80", row.low_confidence_fields?.length && "bg-coral/10")}
              >
                {columns.map((column) => (
                  <td key={column.key} className="px-3 py-3 align-top">
                    {String(row[column.key] ?? "-")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
