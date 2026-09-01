from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import pets, tutores
from app.core.config import settings

app = FastAPI(
    title="Geofencing Adaptativo - Backend",
    description="API REST para rastreamento de pets com geofencing adaptativo (TCC)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.lista_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tutores.router)
app.include_router(pets.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}