from dataclasses import dataclass


# Shared data models — serializable dataclasses passed between workflow and activities. Tempporal serializes data passed between workflows and activities
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


# Workflow result — returned to the caller after workflow completes
@dataclass
class WorkflowResult:
    bill: BillData
    email_status: str  # "sent" | "rejected" | "timed_out" | "failed"
    archive_status: str  # "archived" | "failed"
