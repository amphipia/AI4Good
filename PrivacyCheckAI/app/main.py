from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.metadata import router as metadata_router

from app.routes.faces import router as faces_router

from app.routes.qr import router as qr_router

from app.routes.text import router as text_router

from app.routes.plates import router as plates_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(
    title="PrivChk AI",
    description="AI-powered privacy scanner for images and screenshots",
    version="0.3.0",
)


@app.get("/")
def root():
    return {
        "app": "PrivChk AI",
        "status": "running",
        "ui": "/ui",
        "version": "0.3.0",
    }

@app.get("/ui")
def ui():
    return FileResponse(
        STATIC_DIR / "index.html"
    )


app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static",
)

app.include_router(
    metadata_router,
    prefix="/api/metadata",
    tags=["Metadata"]
)

app.include_router(
    faces_router,
    prefix="/api/faces",
    tags=["Faces"],
)

app.include_router(
    qr_router,
    prefix="/api/qr",
    tags=["QR Codes"],
)

app.include_router(
    text_router,
    prefix="/api/text",
    tags=["Text / PII"],
)

app.include_router(
    plates_router,
    prefix="/api/plates",
    tags=["License Plates"],
)