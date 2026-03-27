# src/services/extractor_service.py
import logging
import os

from src.core.models import ExtractionResult
from src.services.gemini_extractor import GeminiExtractor
from src.services.ollama_extractor import OllamaExtractor
from src.services.regex_extractor import RegexExtractor

logger = logging.getLogger(__name__)


class ClinicalExtractorService:
    """Orchestrator that selects and invokes the appropriate extraction engine.

    Engine priority (configurable via ``APP_MODE`` env var or per-request
    ``mode_override``):

    - ``gemini_api``: Google Gemini with automatic regex fallback.
    - ``local``: Ollama (Mistral) for air-gapped / privacy-sensitive deployments.
    - ``regex``: Deterministic pattern matching, always available.
    """

    def __init__(self) -> None:
        self._mode = os.getenv("APP_MODE", "gemini_api").lower()
        api_key = os.getenv("GEMINI_API_KEY")
        self._gemini = GeminiExtractor(api_key) if api_key else None
        self._regex = RegexExtractor()
        self._ollama = OllamaExtractor()

        if not self._gemini and self._mode == "gemini_api":
            logger.warning(
                "GEMINI_API_KEY not set — requests in gemini_api mode will "
                "fall back to the regex engine automatically."
            )

    async def process_text(
        self,
        text: str,
        mode_override: str | None = None,
        language: str | None = "auto",
    ) -> ExtractionResult:
        """Route a dictation to the configured extraction engine.

        Args:
            text: Raw medical dictation text.
            mode_override: Per-request engine override. Supersedes ``APP_MODE``.
            language: Language hint passed through to the chosen engine.

        Returns:
            Structured ExtractionResult populated by the selected engine.

        Raises:
            ValueError: If ``text`` is empty.
        """
        if not text:
            raise ValueError("Input text cannot be empty.")

        mode = (mode_override or self._mode).lower()

        if mode == "local":
            try:
                result = await self._ollama.extract(text, language)
                result.extractor_type = "LOCAL (Ollama)"
                return result
            except Exception:
                logger.exception("Ollama extraction failed, falling back to regex.")
                result = await self._regex.extract(text, language)
                result.extractor_type = "REGEX (Fallback - Local Error)"
                return result

        if mode == "gemini_api":
            if not self._gemini:
                result = await self._regex.extract(text, language)
                result.extractor_type = "REGEX (Fallback - No Key)"
                return result
            try:
                result = await self._gemini.extract(text, language)
                result.extractor_type = "GEMINI_API"
                return result
            except Exception as e:
                logger.exception("Gemini extraction failed, falling back to regex.")
                result = await self._regex.extract(text, language)
                result.extractor_type = "REGEX (Fallback - API Error)"
                return result

        result = await self._regex.extract(text, language)
        result.extractor_type = "REGEX"
        return result