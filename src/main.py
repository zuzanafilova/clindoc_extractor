import logging
from fastapi import FastAPI
from dotenv import load_dotenv
from src.api.routes import router
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MedBrain ClinDoc Extractor",
    version="1.0.0"
)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
