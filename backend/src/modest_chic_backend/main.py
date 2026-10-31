"""FastAPI application factory and cross-cutting request security."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis

from modest_chic_backend.api.v1.admin_notifications import router as admin_notifications_router
from modest_chic_backend.api.v1.admin_reviews import router as admin_reviews_router
from modest_chic_backend.api.v1.admin_staff import router as admin_staff_router
from modest_chic_backend.api.v1.analytics import router as analytics_router
from modest_chic_backend.api.v1.auth import router as auth_router
from modest_chic_backend.api.v1.auth import staff_router
from modest_chic_backend.api.v1.cart import router as cart_router
from modest_chic_backend.api.v1.catalog import router as catalog_router
from modest_chic_backend.api.v1.checkout import router as checkout_router
from modest_chic_backend.api.v1.cod_confirmation import router as cod_confirmation_router
from modest_chic_backend.api.v1.coupons import router as coupons_router
from modest_chic_backend.api.v1.customer_auth import router as customer_auth_router
from modest_chic_backend.api.v1.customers import router as customers_router
from modest_chic_backend.api.v1.discovery import router as discovery_router
from modest_chic_backend.api.v1.inventory import router as inventory_router
from modest_chic_backend.api.v1.manual_orders import router as manual_orders_router
from modest_chic_backend.api.v1.orders import router as orders_router
from modest_chic_backend.api.v1.policies import public_router as public_policies_router
from modest_chic_backend.api.v1.policies import router as policies_router
from modest_chic_backend.api.v1.reviews import router as reviews_router
from modest_chic_backend.api.v1.settings import router as settings_router
from modest_chic_backend.core.csrf import verify_csrf_token
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.logging import configure_logging
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database

LOGGER = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application with isolated settings and resource lifecycles."""
    configured_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        database = Database(str(configured_settings.database_url))
        redis = Redis.from_url(str(configured_settings.redis_url), decode_responses=True)
        application.state.database = database
        application.state.redis = redis
        try:
            yield
        finally:
            await redis.aclose()
            await database.dispose()

    application = FastAPI(title="Modest Chic API", version="0.1.0", lifespan=lifespan)
    application.state.settings = configured_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured_settings.trusted_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key"],
    )
    application.middleware("http")(enforce_auth_request_security)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(staff_router, prefix="/api/v1")
    application.include_router(admin_staff_router, prefix="/api/v1")
    application.include_router(analytics_router, prefix="/api/v1")
    application.include_router(settings_router, prefix="/api/v1")
    application.include_router(policies_router, prefix="/api/v1")
    application.include_router(public_policies_router, prefix="/api/v1")
    application.include_router(cart_router, prefix="/api/v1")
    application.include_router(checkout_router, prefix="/api/v1")
    application.include_router(cod_confirmation_router, prefix="/api/v1")
    application.include_router(catalog_router, prefix="/api/v1")
    application.include_router(coupons_router, prefix="/api/v1")
    application.include_router(manual_orders_router, prefix="/api/v1")
    application.include_router(orders_router, prefix="/api/v1")
    application.include_router(customers_router, prefix="/api/v1")
    application.include_router(customer_auth_router, prefix="/api/v1")
    application.include_router(discovery_router, prefix="/api/v1")
    application.include_router(inventory_router, prefix="/api/v1")
    application.include_router(reviews_router, prefix="/api/v1")
    application.include_router(admin_reviews_router, prefix="/api/v1")
    application.include_router(admin_notifications_router, prefix="/api/v1")

    @application.exception_handler(ApplicationError)
    async def handle_application_error(request: Request, error: ApplicationError) -> JSONResponse:
        """Translate expected domain failures into the stable error envelope."""
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Return liveness without depending on external service availability."""
        return {"status": "ok", "version": application.version}

    @application.get("/health/ready")
    async def readiness(request: Request) -> JSONResponse:
        """Check database and Redis dependencies before receiving traffic."""
        database: Database = request.app.state.database
        redis: Redis = request.app.state.redis
        checks = {"database": "unavailable", "redis": "unavailable"}
        try:
            async with database.session() as session:
                await session.connection()
            checks["database"] = "connected"
        except Exception:
            LOGGER.warning("readiness_dependency_unavailable", extra={"dependency": "database"})
        try:
            await redis.ping()
            checks["redis"] = "connected"
        except Exception:
            LOGGER.warning("readiness_dependency_unavailable", extra={"dependency": "redis"})

        ready = all(status == "connected" for status in checks.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ok" if ready else "not_ready", **checks},
        )

    return application


async def enforce_auth_request_security(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject unsafe auth/admin requests without a trusted origin and CSRF proof."""
    protected_path = request.url.path.startswith(("/api/v1/auth/", "/api/v1/admin/"))
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or not protected_path:
        return await call_next(request)

    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    csrf_cookie = request.cookies.get("mc_csrf", "")
    csrf_header = request.headers.get("x-csrf-token", "")
    valid_origin = origin is not None and origin in settings.trusted_origins
    valid_csrf = (
        csrf_cookie
        and csrf_cookie == csrf_header
        and verify_csrf_token(csrf_cookie, settings.csrf_signing_key.get_secret_value())
    )
    if not valid_origin or not valid_csrf:
        return JSONResponse(
            status_code=403,
            content={
                "code": "CSRF_ORIGIN_REJECTED",
                "message": "Request origin or anti-forgery proof is invalid.",
            },
        )
    return await call_next(request)
