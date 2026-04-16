from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.database import engine, Base
from app.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Protocolos", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API ────────────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api")


# ── Frontend estático ──────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", response_class=FileResponse)
    def serve_frontend():
        return str(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}", response_class=FileResponse)
    def spa_fallback(full_path: str):
        arquivo = FRONTEND_DIR / full_path
        if arquivo.exists() and arquivo.is_file():
            return str(arquivo)
        return str(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    def root():
        return {"status": "online", "message": "Sistema de Protocolos API — frontend não encontrado"}