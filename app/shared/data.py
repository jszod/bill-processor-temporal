from dataclasses import dataclass


@dataclass
class BillData:
    input_file_name: str
    processed_file_name: str
    unit: int
    amount: float
    date_range: str


@dataclass
class TenantData:
    name: str
    email: str


@dataclass
class WorkflowResult:
    bill: BillData
    email_status: str    # "sent" | "rejected" | "timed_out" | "failed"
    archive_status: str  # "archived" | "failed"
