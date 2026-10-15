from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import local_now

ReportType = Literal["lab", "imaging", "prescription", "discharge", "other"]


class MedicalHistoryUpdate(BaseModel):
    blood_group: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    allergies: str = Field(default="", max_length=3000)
    medications: str = Field(default="", max_length=3000)
    conditions: str = Field(default="", max_length=3000)
    surgeries: str = Field(default="", max_length=3000)
    family_history: str = Field(default="", max_length=3000)
    history_reviewed: bool = False
    share_with_doctors: bool = False

    model_config = ConfigDict(extra="forbid")


class MedicalHistoryResponse(MedicalHistoryUpdate):
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ReportFields(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    report_type: ReportType = "other"
    report_date: date | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Enter a report title with at least two characters.")
        return value.strip()

    @field_validator("report_date")
    @classmethod
    def valid_report_date(cls, value):
        if value and value > local_now().date():
            raise ValueError("Report date cannot be in the future.")
        return value


class MedicalReportResponse(ReportFields):
    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    dependent_id: UUID | None = None
    share_with_doctors: bool = True
    model_config = ConfigDict(from_attributes=True)
