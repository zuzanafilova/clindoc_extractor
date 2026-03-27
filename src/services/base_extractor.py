from abc import ABC, abstractmethod
from src.core.models import ExtractionResult

class IClinicalExtractor(ABC):
    """
    Interface for clinical extraction services, it can be 
    implemented by different technologies (LLM, Regex, etc.).
    """
    
    @abstractmethod
    async def extract(self, text: str, language: str | None = "auto") -> ExtractionResult:
        """
        Extract clinical information from medical text.
        
        Args:
            text: Unstructured medical dictation (Czech or English).
            language: Language hint ("cs", "en", or "auto").
            
        Returns:
            Structured ExtractionResult object.
        """
        pass
