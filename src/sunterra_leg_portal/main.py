from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


LOCAL_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


class HealthStatus(BaseModel):
    status: str
    service: str
    version: str


app = FastAPI(title="SunTerra LEG Portal", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        service="sunterra-leg-portal",
        version="0.1.0",
    )
