import pytest
from src.services.regex_extractor import RegexExtractor

# UNIT TESTS for RegexExtractor
# Focus on deterministic pattern matching logic.

@pytest.mark.asyncio
async def test_regex_vitals_extraction():
    extractor = RegexExtractor()
    text = "TK 120/80, SpO2 98%, HR 72 bpm"
    result = await extractor.extract(text)
    
    assert result.vitals.bp == "120/80"
    assert result.vitals.spo2 == "98%"
    assert result.vitals.hr == "72 bpm"

@pytest.mark.asyncio
async def test_regex_date_classification():
    extractor = RegexExtractor()
    # Newer date should be admission, older should be birth date
    text = "Narozen 15.03.1968, prijat dnes 24.03.2026"
    result = await extractor.extract(text)
    
    assert result.patient.birth_date == "1968-03-15"
    assert result.admission_date == "2026-03-24"

@pytest.mark.asyncio
async def test_regex_icd_codes():
    extractor = RegexExtractor()
    text = "Diagnose: I63.9 (Stroke)"
    result = await extractor.extract(text)
    
    assert any(d.code == "I63.9" for d in result.diagnoses)
