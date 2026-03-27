import os
import json
import logging
import google.generativeai as genai
from src.core.models import ExtractionResult, Patient, Vitals, Diagnosis, Medication
from src.services.base_extractor import IClinicalExtractor

# Setup logging for clinical extraction
logger = logging.getLogger(__name__)

class GeminiExtractor(IClinicalExtractor):
    def __init__(self, api_key: str):
        """
        Initializes the Gemini extractor.
        
        Args:
            api_key: The Google Generative AI API Key.
        """
        if not api_key:
            raise ValueError("Gemini API key is required.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def extract(self, text: str, language: str | None = "auto") -> ExtractionResult:
        """Call the Gemini API and parse the structured JSON response.

        Args:
            text: Raw medical dictation in Czech or English.
            language: Language hint (informational — Gemini auto-detects).

        Returns:
            ExtractionResult validated from Gemini's JSON output.

        Raises:
            RuntimeError: If the API call or JSON parsing fails.
        """
        
        prompt = f"""
        Extract clinical information from the following medical dictation (Czech/English).
        Return the result ONLY as a JSON object matching this schema:
        
        {{
            "patient": {{ "name": "Name", "birth_date": "YYYY-MM-DD" }},
            "vitals": {{ "bp": "178/95", "spo2": "97%", "hr": "bpm", "temp": "C" }},
            "diagnoses": [{{ "code": "I63.9", "system": "ICD-10", "text": "Diagnosis Name" }}],
            "medications": [{{ "name": "aspirin", "dose": "100mg", "frequency": "1x daily" }}],
            "admission_date": "YYYY-MM-DD",
            "follow_up": "Optional follow-up info",
            "warnings": ["List of extracted entities that were uncertain"]
        }}

        Notes for dates:
        - Ensure all output dates are in ISO 8601 (YYYY-MM-DD).

        Input Text:
        ---
        {text}
        ---
        
        Return ONLY valid JSON.
        """
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            json_data = json.loads(response.text)
            
            return ExtractionResult.model_validate(json_data)
            
        except Exception as e:
            raise RuntimeError(f"Gemini Extraction failed: {str(e)}")
