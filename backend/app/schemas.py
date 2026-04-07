from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EXPORT_FIELD_ORDER = [
    "source_file",
    "date",
    "agent",
    "customer",
    "sourcing_executive",
    "weave",
    "quality",
    "shafts",
    "marketing_executive",
    "buyer_reference_no",
    "design_no",
    "is_warp_butta",
    "is_weft_butta",
    "is_warp2_sizing_count",
    "is_seersucker",
    "warp_count",
    "warp_rate_per_kg",
    "warp_rate_incl_gst",
    "warp_gst",
    "warp_content",
    "warp_yarn_type",
    "warp_mill",
    "warp_epi_on_loom",
    "weft_count",
    "weft_rate_per_kg",
    "weft_rate_incl_gst",
    "weft_gst",
    "weft_content",
    "weft_yarn_type",
    "weft_mill",
    "weft_ppi",
    "grey_width",
    "epi_on_table",
    "meters_per_120_yards",
    "total_ends",
    "epi_difference",
    "reed_space",
    "warp_crimp_percent",
    "weight_warp1",
    "cost_warp1",
    "composition_warp1",
    "weight_weft1",
    "cost_weft1",
    "composition_weft1",
    "gsm_total_yarn_cost",
    "fabric_total_yarn_cost",
    "fabric_weight_glm_inc_sizing",
    "sizing_per_kg_rate",
    "sizing_per_kg_cost",
    "weaving_charges_rate",
    "weaving_charges_cost",
    "freight_rate",
    "freight_cost",
    "butta_cutting_rate",
    "butta_cutting_cost",
    "yarn_wastage_rate",
    "yarn_wastage_cost",
    "value_loss_interest_rate",
    "value_loss_interest_cost",
    "payment_term",
    "particulars_total_cost",
    "commission_cd_rate",
    "commission_cd_cost",
    "remark",
    "other_cost_if_any_rate",
    "other_cost_if_any_remarks",
    "extra_remarks_if_any",
    "total_price",
    "target_price",
    "weaving_charge_as_per_tp",
    "order_quantity",
    "yarn_requirement_warp1",
    "yarn_requirement_weft1",
    "yarn_requirement_total",
    "cover_factor",
    "batch_id",
    "reviewed_by",
    "reviewed_at",
]


class UploadedFileMeta(BaseModel):
    filename: str
    checksum: str
    size: int


class UploadResponse(BaseModel):
    upload_id: str
    file_count: int
    files: list[UploadedFileMeta]


class ProcessRequest(BaseModel):
    upload_id: str
    batch_size: int | None = Field(default=None, ge=1, le=100)
    confidence_threshold: float | None = Field(default=None, ge=0, le=100)
    export_name: str | None = Field(default=None, max_length=120)


class ProcessResponse(BaseModel):
    job_id: str
    upload_id: str
    status: str


class JobActionResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExportEntry(BaseModel):
    job_id: str | None = None
    filename: str
    status: str
    created_at: datetime
    processed_files: int = 0
    total_files: int = 0
    download_url: str


class ExtractedRow(BaseModel):
    image_name: str
    source_file: str | None = None
    date: str | None = None
    agent: str | None = None
    customer: str | None = None
    sourcing_executive: str | None = None
    weave: str | None = None
    quality: str | None = None
    shafts: str | None = None
    marketing_executive: str | None = None
    buyer_reference_no: str | None = None
    design_no: str | None = None
    is_warp_butta: bool | None = False
    is_weft_butta: bool | None = False
    is_warp2_sizing_count: bool | None = False
    is_seersucker: bool | None = False
    warp_count: str | None = None
    warp_rate_per_kg: str | None = None
    warp_rate_incl_gst: str | None = None
    warp_gst: str | None = None
    warp_content: str | None = None
    warp_yarn_type: str | None = None
    warp_mill: str | None = None
    warp_epi_on_loom: str | None = None
    weft_count: str | None = None
    weft_rate_per_kg: str | None = None
    weft_rate_incl_gst: str | None = None
    weft_gst: str | None = None
    weft_content: str | None = None
    weft_yarn_type: str | None = None
    weft_mill: str | None = None
    weft_ppi: str | None = None
    grey_width: str | None = None
    epi_on_table: str | None = None
    meters_per_120_yards: str | None = None
    total_ends: str | None = None
    epi_difference: str | None = None
    reed_space: str | None = None
    warp_crimp_percent: str | None = None
    weight_warp1: str | None = None
    cost_warp1: str | None = None
    composition_warp1: str | None = None
    weight_weft1: str | None = None
    cost_weft1: str | None = None
    composition_weft1: str | None = None
    gsm_total_yarn_cost: str | None = None
    fabric_total_yarn_cost: str | None = None
    fabric_weight_glm_inc_sizing: str | None = None
    sizing_per_kg_rate: str | None = None
    sizing_per_kg_cost: str | None = None
    weaving_charges_rate: str | None = None
    weaving_charges_cost: str | None = None
    freight_rate: str | None = None
    freight_cost: str | None = None
    butta_cutting_rate: str | None = None
    butta_cutting_cost: str | None = None
    yarn_wastage_rate: str | None = None
    yarn_wastage_cost: str | None = None
    value_loss_interest_rate: str | None = None
    value_loss_interest_cost: str | None = None
    payment_term: str | None = None
    particulars_total_cost: str | None = None
    commission_cd_rate: str | None = None
    commission_cd_cost: str | None = None
    remark: str | None = None
    other_cost_if_any_rate: str | None = None
    other_cost_if_any_remarks: str | None = None
    extra_remarks_if_any: str | None = None
    total_price: str | None = None
    target_price: str | None = None
    weaving_charge_as_per_tp: str | None = None
    order_quantity: str | None = None
    yarn_requirement_warp1: str | None = None
    yarn_requirement_weft1: str | None = None
    yarn_requirement_total: str | None = None
    cover_factor: str | None = None
    batch_id: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    ocr_engine: str = "tesseract"
    ocr_confidence: float = 0.0
    status: str = "SUCCESS"
    error_message: str | None = None
    low_confidence_fields: list[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    upload_id: str
    status: Literal["pending", "running", "paused", "stopped", "completed", "failed"] = "pending"
    total_files: int = 0
    processed_files: int = 0
    progress: float = 0.0
    message: str = "Job created."
    output_filename: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    logs: list[str] = Field(default_factory=list)
    results: list[ExtractedRow] = Field(default_factory=list)
    failed_images: list[str] = Field(default_factory=list)
