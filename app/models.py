from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

DocCategory = Literal["passport", "diagnostics", "schedule", "defects"]
ConditionState = Literal["good", "attention", "critical"]
DefectSeverity = Literal["low", "medium", "high", "critical"]
DefectStatus = Literal["open", "resolved"]


class DocumentFile(BaseModel):
    filename: str
    category: DocCategory
    category_title: str
    size_bytes: int
    size_human: str
    modified_at: str
    download_url: str
    view_url: str


class MaintenanceMaterialInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(default="", max_length=100)
    unit: str = Field(default="шт.", max_length=30)
    qty_required: float = Field(..., gt=0)
    qty_in_stock: float = Field(default=0.0, ge=0)
    unit_price_rub: float = Field(default=0.0, ge=0)


class MaintenanceMaterial(MaintenanceMaterialInput):
    id: str


class MaintenanceTaskInput(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=1, max_length=240)
    interval_days: int = Field(..., ge=1, le=3650)
    last_completed_date: Optional[str] = None
    next_due_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    responsible: str = Field(default="Служба главного механика", max_length=160)
    service_cost_rub: float = Field(default=0.0, ge=0)
    materials: list[MaintenanceMaterialInput] = Field(default_factory=list)
    notes: str = Field(default="", max_length=600)


class MaintenanceTask(BaseModel):
    id: str
    code: str
    title: str
    interval_days: int
    last_completed_date: Optional[str] = None
    next_due_date: str
    responsible: str = "Служба главного механика"
    service_cost_rub: float = 0.0
    materials: list[MaintenanceMaterial] = Field(default_factory=list)
    notes: str = ""


class CompleteMaintenanceInput(BaseModel):
    performer: str = Field(default="Дежурный инженер", max_length=160)
    comment: str = Field(default="", max_length=500)
    completed_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    restock_used_materials: bool = False


class MaintenanceLogEntry(BaseModel):
    id: str
    task_code: str
    task_title: str
    completed_at: str
    performer: str = ""
    actual_cost_rub: float = 0.0
    comment: str = ""


class DefectInput(BaseModel):
    node: str = Field(..., min_length=1, max_length=180)
    description: str = Field(..., min_length=1, max_length=1000)
    severity: DefectSeverity = "medium"
    recommended_action: str = Field(default="Выполнить ремонт / замену узла", max_length=400)
    estimated_cost_rub: float = Field(default=0.0, ge=0)
    photo_filename: Optional[str] = None


class DefectItem(DefectInput):
    id: str
    created_at: str
    status: DefectStatus = "open"


class PhotoInspection(BaseModel):
    id: str
    filename: str
    created_at: str
    condition: ConditionState = "good"
    node: str = ""
    comment: str = ""
    url: str = ""
    size_human: str = ""


class EquipmentCreateInput(BaseModel):
    id: Optional[str] = Field(default=None, max_length=80)
    name: str = Field(..., min_length=2, max_length=200)
    inventory_number: str = Field(..., min_length=1, max_length=80)
    model: str = Field(default="", max_length=140)
    serial_number: str = Field(default="", max_length=100)
    manufacturer: str = Field(default="", max_length=140)
    commission_year: Optional[int] = Field(default=None, ge=1950, le=2100)
    location: str = Field(..., min_length=1, max_length=200)
    status: ConditionState = "good"


class EquipmentRecord(BaseModel):
    id: str
    name: str
    inventory_number: str
    model: str = ""
    serial_number: str = ""
    manufacturer: str = ""
    commission_year: Optional[int] = None
    location: str
    status: ConditionState = "good"
    maintenance_tasks: list[MaintenanceTask] = Field(default_factory=list)
    maintenance_history: list[MaintenanceLogEntry] = Field(default_factory=list)
    defects: list[DefectItem] = Field(default_factory=list)
    photos: list[PhotoInspection] = Field(default_factory=list)
