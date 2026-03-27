# src/api/routes.py
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from src.core.models import ExtractionResult
from src.services.extractor_service import ClinicalExtractorService

logger = logging.getLogger(__name__)
router = APIRouter()

def get_extractor() -> ClinicalExtractorService:
    return ClinicalExtractorService()


class ExtractRequest(BaseModel):
    """Request payload for the clinical extraction endpoint.

    Attributes:
        text: Raw medical dictation text (Czech or English).
        language: Optional language hint. One of "cs", "en", or "auto".
    """

    text: str
    language: str | None = "auto"


@router.post("/extract", response_model=ExtractionResult)
async def extract_clinical_info(
    request: ExtractRequest,
    service: ClinicalExtractorService = Depends(get_extractor),
    mode: str | None = Query(
        None,
        description="Override extraction engine: gemini_api | local | regex",
    ),
) -> ExtractionResult:
    """Extract structured clinical data from unstructured medical text.

    Args:
        request: Validated request body containing the dictation text.
        service: ClinicalExtractorService object.
        mode: Optional query parameter to override the configured extraction engine.

    Returns:
        ExtractionResult with patient info, vitals, diagnoses, and medications.

    Raises:
        HTTPException(400): If the input text is empty.
        HTTPException(500): If extraction fails unexpectedly.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Input text is empty.")

    try:
        return await service.process_text(
            request.text,
            mode_override=mode,
            language=request.language,
        )
    except Exception as exc:
        logger.exception("Extraction failed for request.")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc


@router.get("/")
def read_root() -> dict:
    """Health-check endpoint returning service metadata."""
    return {
        "service": "MedBrain ClinDoc Extractor",
        "version": "1.0.0",
        "status": "ready",
    }