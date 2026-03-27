import re
from src.core.models import ExtractionResult, Patient, Vitals, Diagnosis, Medication
from src.services.base_extractor import IClinicalExtractor


class MockExtractor(IClinicalExtractor):
    """
    Returns predefined results for the sample dictations in the assignment.
    """
    
    async def extract(self, text: str, language: str | None = "auto") -> ExtractionResult:

        if "Jan Novak" in text or "Jan Novák" in text:
            return ExtractionResult(
                patient=Patient(name="Jan Novak", birth_date="1968-03-15"),
                vitals=Vitals(bp="178/95", spo2="97%"),
                diagnoses=[Diagnosis(code="I63.9", system="ICD-10", text="akutni ischemickou CMP")],
                medications=[
                    Medication(name="aspirin", dose="100mg", frequency="1x denne"),
                    Medication(name="atorvastatin", dose="40mg", frequency="1x daily")
                ],
                admission_date="2024-11-12",
                follow_up="rehab program a kontrola u neurologa za 6 tydnu",
                warnings=["Mocked response for 'Jan Novak' sample."]
            )
            
        elif "Maria Horakova" in text or "Pt. Maria" in text:
            return ExtractionResult(
                patient=Patient(name="Maria Horakova", birth_date="1975-07-22"),
                vitals=Vitals(bp="145/88", spo2="94%", hr="92 bpm"),
                diagnoses=[Diagnosis(code="I21.4", system="ICD-10", text="suspected NSTEMI")],
                medications=[
                    Medication(name="heparin", dose="5000 IU", frequency="bolus"),
                    Medication(name="metoprolol", dose="25mg", frequency="BID")
                ],
                admission_date=None,
                follow_up="cardiology, admission recommended",
                warnings=["Mocked response for 'Maria Horakova' sample."]
            )
            
        return ExtractionResult(
            patient=Patient(name="Unknown", birth_date=None),
            vitals=Vitals(bp=None, spo2=None),
            diagnoses=[],
            medications=[],
            warnings=["Mocked data not found for this input."]
        )
