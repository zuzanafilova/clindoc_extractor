import pytest
import json
import atexit
import os
import re
from typing import Any, Optional
from src.services.extractor_service import ClinicalExtractorService
from src.core.models import ExtractionResult

# INTEGRATION BENCHMARK for ClinicalExtractorService

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

benchmark_results = {}

class EvaluationStats:
    def __init__(self):
        self.matches = 0
        self.missing = 0
        self.wrong = 0
        self.total = 0

    def add_result(self, actual: Any, expected: Any, field_name: str, is_fuzzy: bool = False):
        if expected is None:
            return

        self.total += 1

        # Check for missing
        if not actual:
            print(f"  ⚠️ [MISSING] {field_name:20}: Expected '{expected}'")
            self.missing += 1
            return

        # Comparison logic
        matched = False
        actual_str = str(actual).strip()
        expected_str = str(expected).strip()

        if is_fuzzy:
            matched = self.fuzzy_match(actual_str, expected_str)
        else:
            # Stricter normalization for vitals/doses - removing all whitespace
            actual_norm = re.sub(r'\s+', '', actual_str).lower()
            expected_norm = re.sub(r'\s+', '', expected_str).lower()
            matched = actual_norm == expected_norm

        if matched:
            self.matches += 1
        else:
            print(f"  ❌ [WRONG]   {field_name:20}: Found '{actual}', Expected '{expected}'")
            self.wrong += 1

    @staticmethod
    def fuzzy_match(found, expected):
        if not found or not expected: return False

        # 1. Normalize for whitespace-independent comparison (Step 1: exact clean)
        f_norm = str(found).lower()
        e_norm = str(expected).lower()
        f_clean = re.sub(r'\s+', '', f_norm)
        e_clean = re.sub(r'\s+', '', e_norm)

        if f_clean == e_clean or e_clean in f_clean:
            return True

        # 2. Word-based overlap for diagnoses/names (Step 2: tokens)
        f_words = set(re.findall(r'\w+', f_norm))
        e_words = set(re.findall(r'\w+', e_norm))

        stop_words = {
            'v', 'na', 'u', 's', 'z', 'do', 'o', 'k', 'pro', 'za', 'při', 'nad', 'pod', 'mezi',
            'a', 'i', 'ani', 'nebo', 'ale', 'však', 'že', 'protože', 'pokud',
            'stav', 'st', 'post', 'po', 'v.s', 'suspektní', 'podezření', 'pravděpodobně', 'akutní', 'chronický',
            'in', 'on', 'at', 'with', 'from', 'to', 'for', 'by', 'of', 'and', 'or', 'but', 'yet', 'so',
            'the', 'a', 'an',
            'status', 'post', 'suspected', 'likely', 'acute', 'chronic', 'history', 'known'
        }

        f_words -= stop_words
        e_words -= stop_words

        overlap = f_words.intersection(e_words)
        return len(overlap) >= 1

@pytest.fixture
def service():
    return ClinicalExtractorService()

async def run_benchmark(service, input_file, expected_file, strategy_stats, mode: Optional[str] = None):
    with open(os.path.join(DATA_DIR, input_file), "r") as f:
        input_data = json.load(f)
    with open(os.path.join(DATA_DIR, expected_file), "r") as f:
        expected = json.load(f)

    result: ExtractionResult = await service.process_text(input_data["text"], mode_override=mode)
    file_stats = EvaluationStats()

    print(f"\n===== BENCHMARK REPORT: {input_file} =====")
    print(f"Strategy: {result.extractor_type}")
    print("-" * 50)

    # 1. Patient Info
    file_stats.add_result(result.patient.name, expected['patient'].get('name'), "Patient Name", is_fuzzy=True)
    file_stats.add_result(result.patient.birth_date, expected['patient'].get('birth_date'), "Birth Date")
    file_stats.add_result(result.admission_date, expected.get('admission_date'), "Admission Date")

    # 2. Vitals
    v_exp = expected.get('vitals', {})
    file_stats.add_result(result.vitals.bp, v_exp.get('bp'), "Vital: BP")
    file_stats.add_result(result.vitals.spo2, v_exp.get('spo2'), "Vital: SpO2")
    file_stats.add_result(result.vitals.hr, v_exp.get('hr'), "Vital: HR")

    # 3. Diagnoses (Code + Text)
    matched_diag_indices = set()
    for ed in expected['diagnoses']:
        match_idx = next(
            (i for i, fd in enumerate(result.diagnoses) if fd.code == ed['code'] and i not in matched_diag_indices),
            None)
        if match_idx is not None:
            match = result.diagnoses[match_idx]
            matched_diag_indices.add(match_idx)
            file_stats.add_result(match.code, ed['code'], f"Diag Code ({ed['code']})")
            file_stats.add_result(match.text, ed.get('text'), f"Diag Text ({ed['code']})", is_fuzzy=True)
        else:
            file_stats.add_result(None, ed['code'], f"Diag Code ({ed['code']})")
            file_stats.add_result(None, ed.get('text'), f"Diag Text ({ed['code']})", is_fuzzy=True)

    # 4. Medications (Name + Dose + Frequency)
    matched_med_indices = set()
    for em in expected['medications']:
        match_idx = next((i for i, fm in enumerate(result.medications)
                          if i not in matched_med_indices and EvaluationStats.fuzzy_match(fm.name, em['name'])), None)

        if match_idx is not None:
            match = result.medications[match_idx]
            matched_med_indices.add(match_idx)
            file_stats.add_result(match.name, em['name'], f"Med Name ({em['name']})", is_fuzzy=True)
            file_stats.add_result(match.dose, em.get('dose'), f"Med Dose ({em['name']})", is_fuzzy=True)
            file_stats.add_result(match.frequency, em.get('frequency'), f"Med Freq ({em['name']})", is_fuzzy=True)
        else:
            file_stats.add_result(None, em['name'], f"Med Name ({em['name']})", is_fuzzy=True)
            file_stats.add_result(None, em.get('dose'), f"Med Dose ({em['name']})", is_fuzzy=True)
            file_stats.add_result(None, em.get('frequency'), f"Med Freq ({em['name']})", is_fuzzy=True)

    # 5. Follow-up
    file_stats.add_result(result.follow_up, expected.get('follow_up'), "Follow-up", is_fuzzy=True)

    # Summary for this file
    file_score = (file_stats.matches / file_stats.total) * 100 if file_stats.total > 0 else 0
    print(f"\nFINAL SUMMARY (Score: {file_score:2.1f}%):\n")
    print(f"✅ Matches :  {file_stats.matches} / {file_stats.total}")
    print(f"⚠️ Missing :  {file_stats.missing}")
    print(f"❌ Wrong   :  {file_stats.wrong}")
    print("\n==================================================\n")

    # Update strategy stats
    strategy_stats.matches += file_stats.matches
    strategy_stats.missing += file_stats.missing
    strategy_stats.wrong += file_stats.wrong
    strategy_stats.total += file_stats.total


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["regex", "local"])
async def test_all_benchmarks(service, mode):
    stats = EvaluationStats()
    await run_benchmark(service, "test_data_1.json", "expected_1.json", stats, mode=mode)
    await run_benchmark(service, "test_data_2.json", "expected_2.json", stats, mode=mode)
    await run_benchmark(service, "test_data_3.json", "expected_3.json", stats, mode=mode)
    benchmark_results[mode] = stats

def print_final_table():
    if not benchmark_results:
        return
    print("\n" + "=" * 75)
    print("         FINAL CLINICAL EXTRACTION BENCHMARK SUMMARY")
    print("=" * 75)
    header = f"{'STRATEGY':<20} | {'SCORE':<8} | {'MATCH':<8} | {'MISS':<8} | {'WRONG':<8}"
    print(header)
    print("-" * len(header))
    for mode in ["regex", "local", "gemini_api"]:
        if mode in benchmark_results:
            stats = benchmark_results[mode]
            score = (stats.matches / stats.total * 100) if stats.total > 0 else 0
            row = f"{mode.upper():<20} | {score:6.1f}% | {stats.matches:<8} | {stats.missing:<8} | {stats.wrong:<8}"
            print(row)
    print("=" * 75 + "\n")

atexit.register(print_final_table)
