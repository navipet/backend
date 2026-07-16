from fastapi import FastAPI

from app.api import pets

app = FastAPI(
    title="Geofencing Adaptativo - Backend",
    description="API REST para rastreamento de pets com geofencing adaptativo (TCC)",
    version="0.1.0",
)

app.include_router(pets.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}