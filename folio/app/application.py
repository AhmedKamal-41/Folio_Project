from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import MAX_REQUEST_BYTES, STATIC_DIR, load_settings
from app.database import initialize_database
from app.middleware import RequestSizeLimit, security_headers
from app.routes import documents, health, sharing, users


def create_app(database_path=None):
    settings = load_settings(database_path)

    @asynccontextmanager
    async def lifespan(application):
        initialize_database(settings.database_path)
        yield

    application = FastAPI(title="Folio", version="1.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(RequestSizeLimit, max_bytes=MAX_REQUEST_BYTES)
    application.middleware("http")(security_headers)
    for router in (health.router, users.router, documents.router, sharing.router):
        application.include_router(router, prefix="/api")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application
