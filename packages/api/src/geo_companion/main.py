"""FastAPI entrypoint for the loopback-only local service."""

from fastapi import FastAPI

app = FastAPI(title="Geo Companion API", version="0.1.0")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Report that the local API process is accepting requests."""
    return {"status": "ok", "service": "geo-companion"}
