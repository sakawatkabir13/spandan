from datetime import date
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

OFFICIAL_SOURCE_HOSTS = frozenset(
    {
        "www.evercarebd.com",
        "ibnsinahospitalsylhet.com.bd",
        "appointment.ibfbd.org",
        "www.goodhealthhospital.care",
        "nexushospitalmymensingh.com",
        "old.populardiagnostic.com",
    }
)
DIVISIONS = frozenset(
    {"Dhaka", "Chattogram", "Sylhet", "Rajshahi", "Rangpur", "Mymensingh", "Khulna", "Barishal"}
)


class DirectoryImportRow(BaseModel):
    """Curated public facts only; this schema cannot grant accounts or bookings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    listing_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9-]+$")
    full_name: str = Field(min_length=2, max_length=200)
    native_name: str | None = Field(None, max_length=200)
    specialty: str = Field(min_length=2, max_length=100)
    qualifications: str | None = Field(None, max_length=500)
    institution: str = Field(min_length=2, max_length=200)
    division: str
    district: str = Field(min_length=2, max_length=80)
    address: str | None = Field(None, max_length=1000)
    appointment_phone: str | None = Field(None, pattern=r"^\+?[0-9]{5,15}$")
    published_hours: str | None = Field(None, max_length=300)
    source_url: str = Field(max_length=1000)
    contact_source_url: str | None = Field(None, max_length=1000)
    source_checked_on: date

    @field_validator("division")
    @classmethod
    def known_division(cls, value):
        if value not in DIVISIONS:
            raise ValueError("Unknown Bangladesh division")
        return value

    @field_validator("source_url", "contact_source_url")
    @classmethod
    def official_url(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in OFFICIAL_SOURCE_HOSTS
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Source must be an approved official hospital HTTPS URL")
        return value


class DirectoryDoctorResponse(BaseModel):
    id: UUID
    full_name: str
    native_name: str | None = None
    specialty: str
    qualifications: str | None = None
    institution: str
    division: str
    district: str
    address: str | None = None
    appointment_phone: str | None = None
    published_hours: str | None = None
    source_url: str
    contact_source_url: str | None = None
    source_checked_on: date
    is_active: bool
    demo_doctor_id: UUID | None = None
    booking_status: Literal["contact_hospital", "demo_only"] = "contact_hospital"
    model_config = ConfigDict(from_attributes=True)


class DirectoryVisibilityRequest(BaseModel):
    is_active: bool
