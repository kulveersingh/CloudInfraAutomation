from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.api.change_router import ChangeRouter
from app.api.landing_zone_router import LandingZoneRouter
from app.api.network_router import NetworkRouter
from app.api.release_router import ReleaseRouter
from app.api.routers import CatalogRouter, HealthRouter, ProjectRouter, RegistryRouter
from app.config import Settings
from app.db.database import Database
from app.errors import DomainError
from app.synth.blocks.cloudformation import CloudFormationSchemaCatalog
from app.synth.blocks.registry import BlockRegistry
from app.synth.catalog import ServiceCatalog
from app.synth.synthesizer import ENGINE_VERSION

TITLE = "CloudInfra Platform API"
LOCAL_MODE = "local"


class ErrorTranslator:
    """Turns domain errors into JSON responses with the status code each error type declares."""

    async def domain_error(self, request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.message})


class ApplicationFactory:
    def __init__(self, settings: Settings, session_factory: sessionmaker | None = None):
        self._settings = settings
        self._session_factory = session_factory or Database(settings.sqlalchemy_url()).session_factory

    def create(self) -> FastAPI:
        app = FastAPI(title=TITLE, version=ENGINE_VERSION)
        app.state.session_factory = self._session_factory
        app.state.settings = self._settings
        app.add_middleware(CORSMiddleware, allow_origins=self._settings.cors_origins, allow_methods=["*"],
                           allow_headers=["*"])
        app.add_exception_handler(DomainError, ErrorTranslator().domain_error)
        for router in self._routers():
            app.include_router(router.router)
        return app

    def _routers(self) -> list:
        catalog = CatalogRouter(ServiceCatalog(BlockRegistry.default()), CloudFormationSchemaCatalog.bundled())
        local = self._settings.github_mode == LOCAL_MODE
        return [HealthRouter(), catalog, RegistryRouter(), ProjectRouter(), ChangeRouter(simulation_enabled=local),
                ReleaseRouter(simulation_enabled=local), NetworkRouter(), LandingZoneRouter()]
