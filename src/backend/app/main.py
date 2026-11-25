from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.contexts.alerts.api.router import router as alerts_router
from app.contexts.analytics.api.router import collections_router, insights_router
from app.contexts.analytics.api.router import router as analytics_router
from app.contexts.customers.api.router import router as customers_router
from app.contexts.identity.api.router import router as identity_router
from app.contexts.identity.infrastructure.login_throttle import LoginThrottle
from app.contexts.ledger.api.router import router as ledger_router
from app.contexts.loyalty.api.router import router as loyalty_router
from app.contexts.simulation.api.router import router as simulation_router
from app.shared.api.errors import register_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Merchant Pay API", version="0.1.0",
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    app.state.login_throttle = LoginThrottle()

    api = APIRouter(prefix="/api/v1")
    api.include_router(identity_router)
    api.include_router(ledger_router)
    api.include_router(analytics_router)
    api.include_router(collections_router)
    api.include_router(insights_router)
    api.include_router(alerts_router)
    api.include_router(simulation_router)
    api.include_router(customers_router)
    api.include_router(loyalty_router)
    app.include_router(api)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
