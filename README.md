# ClinDoc Extractor

NLP service designed to extract structured information from medical dictations in Czech and English. 

Built with **FastAPI**, **Python 3.12**, and **Ollama/Gemini LLM** integration.

---

## Quick Start (Dockerized)

The entire project is containerized for a one-command setup including local LLMs.

### 1. Requirements
-   **Docker** and **Docker Compose** installed.
-   (Optional) **Gemini API Key** in `.env` for cloud extraction.

### 2. Launch the Platform
```bash
docker-compose up --build
```

**Background details:**
-   Starts **API** on port `8000`.
-   Starts a local **Ollama** server.
-   The `ollama-pull` sidecar automatically downloads the `mistral` model.

---

## Quick Start (Local environment)

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## API Usage

Visit **Swagger UI** at: `http://localhost:8000/docs`

### **Supported Extraction Modes**
You can switch the engine on-the-fly via the `mode` parameter:
-   `gemini_api` : Gemini LLM with automatic Regex fallback (Best performance).
-   `local` : Ollama with Mistral model (Best privacy).
-   `regex` : Deterministic pattern matching (Best reliability).

Example: `POST /extract?mode=gemini_api`

---

## Testing & Validation

The test suite is divided into two categories:

### **1. Unit Tests (Logic & API Requirements)**
Tests core business logic, regex patterns, and API error handling (empty input, malformed JSON).
```bash
docker-compose exec clindoc-api pytest tests/unit -v
```

### **2. Quality Evaluator (Performance Benchmarking)**
Evaluates extraction accuracy against Gold Standard samples using fuzzy matching.
```bash
docker-compose exec clindoc-api pytest tests/validation -s
```

Test regex only: 
```bash
docker-compose exec clindoc-api pytest tests/validation -k "regex" -s 
```

*To run all tests at once:* `docker-compose exec clindoc-api pytest -s`

---

## Configuration (`.env`)

-   `APP_MODE`: Default mode (`gemini_api`, `local`, or `regex`).
-   `GEMINI_API_KEY`: API key for Gemini.
-   `OLLAMA_URL`: Connection string (defaults to `http://ollama:11434`).

### **Stack**
-   **Backend:** FastAPI (Python 3.12)
-   **AI Engines:** Google Gemini, Ollama (Mistral)
-   **Testing:** Pytest with Asyncio
-   **DevOps:** Docker Compose

---

## Architecture & Design Decisions

The solution is built using a **Modular Strategy Pattern**. This allows us to decouple the extraction logic from the API and switch between different LLM/Regex providers without changing the core business logic.

### **Orchestration & Fallback Mechanism**
We use a `ClinicalExtractorService` as a central orchestrator. 
-   **Cloud-First (Optional):** We prefer Gemini LLM for highest accuracy in clinical data extraction.
-   **Local-First (Privacy):** We support local Mistral models (via Ollama) for environments requiring data sovereignty.
-   **Deterministic Fallback:** If any LLM fails (due to API quota, networking, or hardware issues), the service automatically rolls back to a **Regex-based Engine**.

---

## AI usage

This project was developed using an AI-augmented workflow via Antigravity (Gemini 3 flash, Gemini 3.1 Pro models).

---

## Limitations

1.  **Regex Engine Scope:** Currently, the Regex fallback does **not** extract diagnoses name. Also regex matching can be insufficient in real world tasks.
2.  **LLM "Hallucinations":** While Gemini 2.5 is highly reliable, it may occasionally misinterpret ambiguous dates without explicit context hints.
3.  **Local Model Latency:** Running Mistral locally on CPU-only hardware may result in higher latency per request.
4.  **LLM Output Formatting Constraints:** Local LLMs (via Ollama) can occasionally wrap their JSON responses in Markdown code blocks (json ... ) or append introductory text. The current parser is strict, meaning unexpected formatting may result in parsing failures. Implementing robust pre-parsing (e.g., regex-based JSON extraction) is recommended.

---

## Future Improvements & Technical Debt

In a real deployment, the following improvements would be prioritized:

1.  **FHIR R4 Mapping:** Implementing a dedicated mapping layer to transform `ExtractionResult` into standardized FHIR Bundles (Observation, Patient, MedicationStatement).
2.  **Security (GDPR/HIPAA):** Integration with an anonymization service to mask PII (Names, Addresses) before data is sent to cloud LLM providers.
3.  **High-Availability (HA):** Using a load balancer and a worker queue (e.g., Celery + Redis) for asynchronous background processing.
4.  **HITL (Human-in-the-loop):** Adding a confidence scoring mechanism where low-confidence fields require manual verification by a clinical clerk.
5.  **Audit Logs:** Storing original dictations and extraction results for clinical auditing and compliance.
6.  **Centralized Configuration Management:** Migrate from scattered os.getenv() calls across the codebase to a centralized, strictly typed configuration class utilizing pydantic-settings. This would ensure fail-fast behavior if critical environment variables are missing during startup.
7.  **Externalized Clinical Resources:** Move business logic constants - such as the hardcoded medication blacklist tokens in the Regex engine - out of the source code and into externalized datasets or databases. This will enable medical data updates without requiring new application deployments.

### **Performance Benchmark Summary**
The service includes a validation suite to measure extraction accuracy against Gold Standard samples.

You can replicate these results with:

```bash
docker-compose exec clindoc-api pytest tests/validation -s
```

```text
===========================================================================
         FINAL CLINICAL EXTRACTION BENCHMARK SUMMARY
===========================================================================
STRATEGY             | SCORE    | MATCH    | MISS     | WRONG   
----------------------------------------------------------------
REGEX                |   92.1% | 35       | 3        | 0       
LOCAL (Ollama)       |  100.0% | 38       | 0        | 0       
===========================================================================
```