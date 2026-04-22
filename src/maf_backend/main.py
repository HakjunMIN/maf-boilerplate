from __future__ import annotations

from fastapi import FastAPI

from maf_backend.api.routes import router


app = FastAPI(title="MAF Analysis Backend")
app.include_router(router)