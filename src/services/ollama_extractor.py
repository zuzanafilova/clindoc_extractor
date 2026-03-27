import json
import httpx
import os
import logging
from src.services.base_extractor import IClinicalExtractor
from src.core.models import ExtractionResult, Patient, Vitals, Diagnosis, Medication

logger = logging.getLogger(__name__)

class OllamaExtractor(IClinicalExtractor):
    """
    Local LLM extractor using Ollama API with JSON mode.
    """

    def __init__(self):
        self.host = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.model = os.getenv("OLLAMA_MODEL", "mistral")

    async def extract(self, text: str, language: str | None = "auto") -> ExtractionResult:
        """Send a dictation to the local Ollama instance and parse the JSON response.

        Args:
            text: Raw medical dictation.
            language: Language hint (unused by Ollama — Mistral auto-detects).

        Returns:
            ExtractionResult populated from Ollama's JSON output, or an empty
            result with a warning on connection/parse failure.
        """
        system_instruction = """
        You are a medical data extraction assistant. 
        Extract facts from the text into a JSON object.
        If a field is unknown, use null.
        
        EXTRACTION RULES:
        - Use EXACT terms from the text for medication dose and frequency 
        (e.g., if text says 'bolus', use 'bolus', do not change it to '1x').
        - Do not summarize or normalize clinical values unless specified.
        
        STRICT FORMATTING RULES:
        - Blood Pressure (bp): Use format 'SYS/DIA' only (e.g., '120/80'). Do NOT include 'mmHg'.
        - Heart Rate (hr): Use format number and bpm (e.g., '70 bpm').
        - SpO2: Use numbers with % (e.g., '95%').
        
        Mandatory JSON structure:
        {
          "patient": {"name": "full Name", "birth_date": "YYYY-MM-DD"},
          "vitals": {"bp": "120/80", "spo2": "95%", "hr": "70 bpm"},
          "admission_date": "YYYY-MM-DD",
          "diagnoses": [{"code": "ICD-10-CODE", "text": "description"}],
          "medications": [{"name": "drug", "dose": "mg", "frequency": "frequency as string"}],
          "follow_up": "next steps"
        }
        """

        try:
            async with httpx.AsyncClient(timeout=360.0) as client:
                response = await client.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "system": system_instruction,
                        "prompt": f"Extract from this text:\n{text}",
                        "stream": False,
                        "format": "json"
                    }
                )
                response.raise_for_status()
                raw_json = response.json().get("response", "{}")
                
                logger.debug(f"DEBUG: Ollama response: {raw_json[:200]}...")
                
                data = json.loads(raw_json)

                p_data = data.get("patient", {})
                v_data = data.get("vitals", {})
                
                return ExtractionResult(
                    patient=Patient(
                        name=p_data.get("name"),
                        birth_date=p_data.get("birth_date")
                    ),
                    vitals=Vitals(
                        bp=v_data.get("bp"),
                        spo2=v_data.get("spo2"),
                        hr=v_data.get("hr")
                    ),
                    diagnoses=[
                        Diagnosis(
                            code=d.get("code"),
                            text=d.get("text")
                        )
                        for d in data.get("diagnoses", [])
                        if isinstance(d, dict) and d.get("code")
                    ],

                    medications=[
                        Medication(
                            name=m.get("name"),
                            dose=m.get("dose"),
                            frequency=m.get("frequency")
                        )
                        for m in data.get("medications", [])
                        if isinstance(m, dict) and m.get("name")
                    ],
                    admission_date=data.get("admission_date"),
                    follow_up=data.get("follow_up"),
                    warnings=["Local LLM Extraction."]
                )

        except Exception as exc:
            logger.exception("Ollama extraction failed.")
            raise exc
