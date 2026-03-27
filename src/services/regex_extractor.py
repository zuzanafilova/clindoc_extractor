# src/services/regex_extractor.py
import logging
import os
import re

from src.core.models import Diagnosis, ExtractionResult, Medication, Patient, Vitals
from src.services.base_extractor import IClinicalExtractor

logger = logging.getLogger(__name__)

# Tokens that appear in drug database entries but are not drug names themselves.
_MED_BLACKLIST: set[str] = {
    "LÉČIVA", "LÉIVA", "LЙИIVA", "ZENTIVA", "SANDOZ", "KRKA", "TEVA",
    "TABLETY", "TBL", "MG", "ML", "ROZTOK", "CPS", "GMBH", "COMP", "SR",
    "DR.MAX", "PLUS", "FORTE", "MITE", "GEL", "MAST", "CREAM", "KAPKY",
    "INJ", "SOL", "SUS", "OPH", "NAS", "VAG", "RECT", "POTAHOVANÉ"
}

class RegexExtractor(IClinicalExtractor):
    """Deterministic clinical entity extractor using regular expressions.

    Designed as a reliable, zero-dependency fallback that works without any
    external API or model. Covers vitals, ICD-10 codes, dates, and medications
    matched against a local drug name dictionary.
    """

    # Shared across instances to avoid re-reading the file on every instantiation.
    _medications_cache: set[str] | None = None

    def __init__(self) -> None:
        self._load_medications()

    def _load_medications(self) -> None:
        """Populate the class-level medication name cache from a flat text file.

        The file is expected at ``src/services/resources/medications.txt``,
        one entry per line. Multi-word brand names are split so individual
        active-substance tokens can also be matched.
        """
        if RegexExtractor._medications_cache is not None:
            return

        med_file = os.path.join(os.path.dirname(__file__), "resources", "medications.txt")
        meds: set[str] = set()

        if os.path.exists(med_file):
            with open(med_file, encoding="utf-8") as fh:
                for line in fh:
                    full_name = line.strip().upper()
                    if not full_name:
                        continue
                    meds.add(full_name)
                    for part in re.split(r"[\s./,]+", full_name):
                        clean = part.strip()
                        if len(clean) > 3 and clean not in _MED_BLACKLIST:
                            meds.add(clean)
        else:
            logger.warning("Medication dictionary not found at %s.", med_file)

        RegexExtractor._medications_cache = meds

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def extract(self, text: str, language: str | None = "auto") -> ExtractionResult:
        """Extract clinical entities from raw medical text using regex patterns.

        Args:
            text: Unstructured medical dictation in Czech or English.
            language: Language hint ("cs", "en", or "auto"). Currently unused
                by the regex engine but kept for interface compatibility.

        Returns:
            Populated ExtractionResult. Fields that could not be extracted
            are left as ``None``.
        """
        return ExtractionResult(
            patient=Patient(name=self._extract_name(text), birth_date=self._extract_dob(text)),
            vitals=self._extract_vitals(text),
            diagnoses=self._extract_diagnoses(text),
            medications=self._extract_medications(text),
            admission_date=self._extract_admission_date(text),
            follow_up=self._extract_follow_up(text),
            extractor_type="REGEX",
            warnings=["Deterministic regex engine — name and medication extraction may be incomplete."],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_date(raw: str) -> str | None:
        """Convert a raw date string to ISO 8601 (YYYY-MM-DD).

        Args:
            raw: Date string with ``.``, ``/``, or ``-`` separators.

        Returns:
            ISO 8601 string, or ``None`` if the format is unrecognised.
        """
        parts = re.split(r"[./-]", raw)
        if len(parts) != 3:
            return None
        if len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        if len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return None

    def _extract_all_dates(self, text: str):
        """Return (match, iso_date) pairs for every date-like token in text."""
        pattern = r"\d{1,2}[./-]\d{1,2}[./-]\d{4}"
        results = []
        for m in re.finditer(pattern, text):
            iso = self._normalise_date(m.group())
            if iso:
                results.append((m, iso))
        return results

    def _extract_dob(self, text: str) -> str | None:
        """Extract the patient's date of birth."""
        date_hits = self._extract_all_dates(text)
        for m, iso in date_hits:
            ctx = text[max(0, m.start() - 40): m.start()].lower()
            if any(k in ctx for k in ("narozeni", "narozen", "dob", "born")):
                return iso
        # Heuristic: earliest date is most likely the birth date.
        if date_hits:
            return min(date_hits, key=lambda x: x[1])[1]
        return None

    def _extract_admission_date(self, text: str) -> str | None:
        """Extract the hospital admission date."""
        date_hits = self._extract_all_dates(text)
        for m, iso in date_hits:
            ctx = text[max(0, m.start() - 40): m.start()].lower()
            if any(k in ctx for k in ("prijat", "admitted", "admission", "prijem")):
                return iso
        # Heuristic: latest date is most likely the admission date.
        if len(date_hits) >= 2:
            return max(date_hits, key=lambda x: x[1])[1]
        return None

    @staticmethod
    def _extract_vitals(text: str) -> Vitals:
        """Parse blood pressure, SpO2, and heart rate from text."""
        bp_m = re.search(
            r"\b(?:BP|TK|TLAK|Pressure)\D{0,3}(\d{2,3}/\d{2,3})(?!/\d{4})\b",
            text, re.IGNORECASE,
        )
        if not bp_m:
            # Fallback: bare NNN/NNN not followed by a year.
            bp_m = re.search(r"\b(\d{2,3}/\d{2,3})(?!/\d{4})\b", text)

        spo2_m = re.search(r"\b(?:SpO2|saturace|sat)\D{0,3}(\d{2,3})\s?%", text, re.IGNORECASE)
        if not spo2_m:
            spo2_m = re.search(r"\b(\d{2,3})\s?%", text)

        hr_m = re.search(r"\b(?:HR|tep|puls|pulse)\D{0,3}(\d{2,3})\b", text, re.IGNORECASE)
        if not hr_m:
            hr_m = re.search(r"\b(\d{2,3})\s?bpm\b", text, re.IGNORECASE)

        return Vitals(
            bp=bp_m.group(1) if bp_m else None,
            spo2=f"{spo2_m.group(1)}%" if spo2_m else None,
            hr=f"{hr_m.group(1)} bpm" if hr_m else None,
        )

    @staticmethod
    def _extract_diagnoses(text: str) -> list[Diagnosis]:
        """Extract ICD-10 codes and their preceding textual descriptions.

        The pattern requires a letter followed by exactly two digits and an
        optional decimal sub-category (e.g. ``I63.9``, ``Z00``). A word
        boundary on both sides prevents false matches on version strings.
        """
        diagnoses: list[Diagnosis] = []
        pattern = r"(?<!\d)\b([A-Z]\d{2}(?:\.\d{1,2})?)\b"
        for m in re.finditer(pattern, text):
            diagnoses.append(Diagnosis(
                code=m.group(1),
                system="ICD-10",
                text=None
            ))
        return diagnoses

    def _extract_medications(self, text: str) -> list[Medication]:
        """Match medication names against the local drug dictionary.

        After each match the matched span is blanked out in the working copy
        of the text to prevent the same substance from being matched twice
        under a different token from the dictionary.

        Returns:
            List of Medication objects with name, dose, and frequency where
            those could be found in the 30 characters following the drug name.
        """
        if not RegexExtractor._medications_cache:
            return []

        found: list[Medication] = []
        upper_text = text.upper()

        for med in sorted(RegexExtractor._medications_cache, key=len, reverse=True):
            if len(med) < 4:
                continue
            m = re.search(rf"\b{re.escape(med)}\b", upper_text)
            if not m:
                continue

            ctx = text[m.end(): m.end() + 30]
            dose_m = re.search(r"(\d+(?:[.,]\d+)?\s?(?:mg|g|ml|IU|ug))", ctx, re.IGNORECASE)
            freq_m = re.search(r"(\d+x\s?den\w+|BID|TID|bolus|1-0-1|1x\s?denně)", ctx, re.IGNORECASE)

            found.append(
                Medication(
                    name=med.capitalize(),
                    dose=dose_m.group(1).strip() if dose_m else None,
                    frequency=freq_m.group(1).strip() if freq_m else None,
                )
            )
            upper_text = upper_text[: m.start()] + " " * len(med) + upper_text[m.end():]

        return found

    @staticmethod
    def _extract_name(text: str) -> str | None:
        """Extract the patient's full name using keyword-anchored patterns.

        Returns:
            Full name string, or ``None`` if no pattern matched.
        """
        cz_u = "A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"
        cz_l = "a-záčďéěíňóřšťúůýž"
        patterns = [
            rf"(?:Pacient|Jméno|Name|Patient|Pt\.?|pac\.?)\s*[:\-]?\s*([{cz_u}][{cz_l}]+\s+[{cz_u}][{cz_l}]+)",
            rf"([{cz_u}][{cz_l}]+\s+[{cz_u}][{cz_l}]+)\s*\([^)]*\d{{4}}[^)]*\)",
            rf"([{cz_u}][{cz_l}]+\s+[{cz_u}][{cz_l}]+),\s*(?:nar\.?|datum narození|born)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_follow_up(text: str) -> str | None:
        """Extract recommended follow-up information.

        Returns:
            Follow-up text, or ``None`` if not found.
        """
        m = re.search(
            r"(?:Doporucen|Referred to|Follow-up):?\s*(.*?)(?:\.|$|Diagnoza|Dx:)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return m.group(1).strip() if m else None