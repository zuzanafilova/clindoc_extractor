from datetime import date
from pydantic import BaseModel, Field


class Patient(BaseModel):
    """Basic patient information."""
    name: str | None = Field(None, description="Patient's full name")
    birth_date: str | None = Field(None, description="ISO 8601 format: YYYY-MM-DD")

class Vitals(BaseModel):
    """Vital signs extracted from dictation."""
    bp: str | None = Field(None, description="Blood pressure (e.g., 120/80)")
    spo2: str | None = Field(None, description="Oxygen saturation in %")
    hr: str | None = Field(None, description="Heart rate in bpm")
    temp: str | None = Field(None, description="Body temperature in Celsius")

class Diagnosis(BaseModel):
    """Diagnosis with ICD-10 code and description."""
    code: str = Field(..., description="ICD-10 code (e.g., I63.9)")
    system: str = Field("ICD-10", description="Classification system")
    text: str | None = Field(None, description="Diagnosis name or description")

class Medication(BaseModel):
    """Prescribed or current medications."""
    name: str = Field(..., description="Medication name (e.g., aspirin)")
    dose: str | None = Field(None, description="Dosage (e.g., 100mg)")
    frequency: str | None = Field(None, description="Frequency (e.g., 1x daily)")

class ExtractionResult(BaseModel):
    """The main response object for the clinical extraction service."""
    patient: Patient
    vitals: Vitals
    diagnoses: list[Diagnosis] = []
    medications: list[Medication] = []
    admission_date: str | None = Field(None, description="ISO 8601 admission date")
    follow_up: str | None = Field(None, description="Recommended follow-up details")
    extractor_type: str = Field("unknown", description="Which strategy was used")
    warnings: list[str] = []