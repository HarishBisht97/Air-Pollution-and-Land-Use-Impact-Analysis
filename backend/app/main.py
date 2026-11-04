from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.naaqs import naaqs_payload

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Research-oriented geospatial API for air quality and land-use analysis. "
        "Observational results are distinguished from satellite indices, classified maps, "
        "statistical estimates, and screening scores."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/v1/health")
def api_health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/v1/naaqs")
def naaqs():
    return naaqs_payload()
