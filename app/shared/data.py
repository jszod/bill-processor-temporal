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
