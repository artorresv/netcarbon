from typing import Any
from fastapi import FastAPI
from routers import timeseries, indices
from db.utils import get_database

tags_metadata = [
    {
        "name": "Time Series",
        "description": "Operations with spectral indices time series",
    },
    {
        "name": "Spectral Indices",
        "description": "Operations with spectral indices"
    }
]

app = FastAPI(
    title="Spatial API",
    summary="Demo of a Web API that provides access to time series data and spectral indices.",
    version="0.0.1",
    openapi_tags=tags_metadata
)


@app.on_event('startup')
async def startup() -> Any:
    await get_database().connect()


@app.on_event('shutdown')
async def shutdown() -> Any:
    await get_database().disconnect()

app.include_router(timeseries.router)
app.include_router(indices.router)
