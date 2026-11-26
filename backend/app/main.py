from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from app.api.routes import router
from app.config import BASE_DIR

app = FastAPI(
    title="UBP Portfolio Statement Extraction System",
    description="Deterministic server-side extraction and financial validation engine for UBP portfolio valuation statements.",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Register API routes first so they are never shadowed by static or SPA handlers
app.include_router(router)

# 2. Configure frontend build static asset serving with explicit cache controls
frontend_dist = BASE_DIR / "frontend" / "dist"
assets_dir = frontend_dist / "assets"

class ImmutableAssetsStaticFiles(StaticFiles):
    """Serves Vite content-hashed /assets/* bundles with immutable cache headers."""
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

def _serve_no_cache_index() -> FileResponse:
    index_path = frontend_dist / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend entrypoint not found.")
    return FileResponse(
        path=str(index_path),
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

if frontend_dist.exists():
    if assets_dir.exists():
        app.mount("/assets", ImmutableAssetsStaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    @app.head("/", include_in_schema=False)
    def serve_frontend_root():
        return _serve_no_cache_index()

    @app.get("/{full_path:path}", include_in_schema=False)
    @app.head("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa_or_static(full_path: str):
        # Never intercept API routes or hashed /assets/* paths with HTML
        if (
            full_path == "api"
            or full_path.startswith("api/")
            or full_path == "assets"
            or full_path.startswith("assets/")
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        # Serve explicit root-level static files (e.g., favicon, robots.txt) safely
        candidate = (frontend_dist / full_path).resolve()
        dist_root = frontend_dist.resolve()
        if str(candidate).startswith(str(dist_root)) and candidate.is_file():
            if candidate.suffix.lower() == ".html":
                return FileResponse(
                    path=str(candidate),
                    media_type="text/html; charset=utf-8",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
            return FileResponse(path=str(candidate))

        # Any missing file request with a file extension must return 404, never HTML
        if "." in Path(full_path).name:
            raise HTTPException(status_code=404, detail="Static asset not found")

        # Valid extensionless client routes resolve to fresh non-cached index.html
        return _serve_no_cache_index()

if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
