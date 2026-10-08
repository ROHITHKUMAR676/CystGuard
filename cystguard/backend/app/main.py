import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.medications import router as medications_router
from app.api.mri import router as mri_router
from app.api.reports import router as reports_router
from app.api.longitudinal import router as longitudinal_router
from app.api.surveillance import router as surveillance_router
from app.api.relationships import router as relationships_router
from app.api.workflow import router as workflow_router
from app.api.food import router as food_router
from app.config import get_settings
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version=settings.app_version)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Keep internal exception details out of API responses.
        logger.exception("Unhandled API exception for %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @application.exception_handler(OperationalError)
    async def database_unavailable_handler(request: Request, exc: OperationalError) -> JSONResponse:
        # Database/driver exceptions can include connection metadata; never log them verbatim.
        logger.error("Database connectivity failure for %s %s", request.method, request.url.path)
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Database operation failed for %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    @application.get(f"{settings.api_prefix}/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.app_version}

    @application.get(f"{settings.api_prefix}/health/database", tags=["system"])
    def database_health(
        db: Session = Depends(get_db),
        _current_user: User = Depends(get_current_user),
    ) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        return {"database": "connected"}

    application.include_router(auth_router, prefix=settings.api_prefix)
    application.include_router(mri_router, prefix=settings.api_prefix)
    application.include_router(reports_router, prefix=settings.api_prefix)
    application.include_router(medications_router, prefix=settings.api_prefix)
    application.include_router(longitudinal_router, prefix=settings.api_prefix)
    application.include_router(surveillance_router, prefix=settings.api_prefix)
    application.include_router(relationships_router, prefix=settings.api_prefix)
    application.include_router(workflow_router, prefix=settings.api_prefix)
    application.include_router(food_router, prefix=settings.api_prefix)
    return application


app = create_app()
